import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import re
import json

# Try importing Google Drive libraries
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False
    st.warning("⚠️ Google Drive libraries not installed. Install them to enable Drive upload.")
    st.info("Add to requirements.txt: google-auth, google-auth-oauthlib, google-api-python-client")

# -------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------
st.set_page_config(page_title="Amazon Finder - Deliverable", layout="wide")
st.title("🛍️ Amazon Product Finder - Pinterest Style + Auto Drive Upload")

# -------------------------------------------------------
# LOAD SECRETS (API KEYS + DRIVE)
# -------------------------------------------------------
try:
    OPENROUTER_API_KEY = str(st.secrets["OPENROUTER_API_KEY"]).strip()
    GROQ_API_KEY = str(st.secrets["GROQ_API_KEY"]).strip()
    SERPAPI_KEY = str(st.secrets.get("SERPAPI_KEY", "")).strip()
    SERVICE_ACCOUNT_JSON = st.secrets["SERVICE_ACCOUNT_JSON"]
except Exception as e:
    st.error(f"❌ Missing Streamlit secrets: {e}")
    st.info("""
    Required secrets:
    - OPENROUTER_API_KEY
    - GROQ_API_KEY
    - SERPAPI_KEY
    - SERVICE_ACCOUNT_JSON (Google Drive service account)
    """)
    st.stop()

# -------------------------------------------------------
# GOOGLE DRIVE SERVICE ACCOUNT LOGIN
# -------------------------------------------------------
drive_service = None

if DRIVE_AVAILABLE:
    try:
        # Handle both string and dict formats
        if isinstance(SERVICE_ACCOUNT_JSON, str):
            service_info = json.loads(SERVICE_ACCOUNT_JSON)
        else:
            service_info = dict(SERVICE_ACCOUNT_JSON)

        creds = service_account.Credentials.from_service_account_info(
            service_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )

        drive_service = build("drive", "v3", credentials=creds)
        st.sidebar.success("✅ Google Drive connected")
    except Exception as e:
        st.sidebar.error(f"❌ Google Drive auth failed: {e}")
        st.sidebar.info("Drive upload will be disabled")
else:
    st.sidebar.warning("⚠️ Google Drive upload disabled (missing libraries)")

# -------------------------------------------------------
# AMAZON AFFILIATE TAG
# -------------------------------------------------------
AFFILIATE_TAG = "passionismyso-20"

def add_affiliate_tag(link):
    """Add Amazon affiliate tag to product link."""
    if not link or "tag=" in link:
        return link
    separator = "&" if "?" in link else "?"
    return f"{link}{separator}tag={AFFILIATE_TAG}"

# -------------------------------------------------------
# TEXT MODELS
# -------------------------------------------------------
all_models = {
    "🔸 Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "🔸 Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "⚡ Llama 3 8B (Groq)": "llama3-8b-8192",
    "✨ Llama 3 70B": "meta-llama/llama-3-70b-instruct",
    "✨ Qwen 2.5 32B": "qwen/qwen-2.5-32b-instruct"
}

model_choice = st.selectbox("🤖 Choose AI Model", list(all_models.keys()))

# -------------------------------------------------------
# PRODUCT INPUT
# -------------------------------------------------------
product_name = st.text_input("🔍 Product Name", placeholder="e.g. wireless headphones")

# Google Drive Folder ID (make it configurable)
drive_folder_id = st.text_input(
    "📁 Google Drive Folder ID (optional)",
    value="1XAJLIDBpWPYk6-xzGahLfdU4cqzkF7Bc",
    help="Leave default or paste your own folder ID"
)

# -------------------------------------------------------
# AMAZON SEARCH FUNCTIONS
# -------------------------------------------------------
def search_serpapi(query):
    """Search Amazon via SerpAPI."""
    if not SERPAPI_KEY:
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "amazon",
        "q": query,  # Fixed: was "k", should be "q"
        "amazon_domain": "amazon.com",
        "api_key": SERPAPI_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=15).json()
        products = []
        
        for item in res.get("organic_results", [])[:1]:  # Get first result
            if item.get("link") and "amazon.com" in item["link"]:
                products.append({
                    "title": item.get("title", "No title"),
                    "asin": item.get("asin", "N/A"),
                    "link": add_affiliate_tag(item["link"]),
                    "image": item.get("thumbnail", ""),
                    "price": item.get("price", "Price not available"),
                })
        
        return products
    except Exception as e:
        st.warning(f"SerpAPI error: {e}")
        return []


def scrape_amazon(query):
    """Fallback: scrape Amazon directly."""
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        page = requests.get(url, headers=headers, timeout=10).text

        asin_match = re.search(r'data-asin="(\w{10})"', page)
        title_match = re.search(
            r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page
        )
        img_match = re.search(r'<img.*?class="s-image".*?src="(.*?)"', page)
        price_match = re.search(r'\$[\d,]+\.?\d{0,2}', page)

        if asin_match and title_match:
            link = f"https://www.amazon.com/dp/{asin_match.group(1)}"
            link = add_affiliate_tag(link)

            return [{
                "asin": asin_match.group(1),
                "title": title_match.group(1).strip(),
                "image": img_match.group(1) if img_match else None,
                "link": link,
                "price": price_match.group(0) if price_match else "N/A"
            }]
        return []
    except Exception as e:
        st.warning(f"Scraper error: {e}")
        return []


def search_amazon_fallback(query):
    """Try SerpAPI first, then fallback to scraping."""
    # Try SerpAPI
    r1 = search_serpapi(query)
    if r1:
        return r1, "SerpAPI 🔥"

    # Try scraping
    r2 = scrape_amazon(query)
    if r2:
        return r2, "Scraper Fallback 🖇️"

    return [], "❌ Nothing Found"

# -------------------------------------------------------
# PINTEREST DESCRIPTION VIA AI
# -------------------------------------------------------
def generate_pinterest_description(product, model_id):
    """Generate Pinterest-style marketing description."""
    prompt = f"""Write a short Pinterest-style promotional description (max 80 words).

Product:
Title: {product["title"]}
ASIN: {product["asin"]}
Price: {product["price"]}

Tone:
• Emotional + lifestyle focused
• Benefits over features
• Add emojis naturally
• Make it compelling and shareable

Keep it under 80 words!"""

    # Choose API based on model
    if model_id == "llama3-8b-8192":  # Groq backend
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
    else:  # OpenRouter
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

    data = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150
    }

    try:
        r = requests.post(url, json=data, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"✨ {product['title']} — A must-have item! Get yours now! (ASIN: {product['asin']})"
    except Exception as e:
        st.warning(f"AI generation error: {e}")
        return f"✨ {product['title']} — A must-have item! Get yours now! (ASIN: {product['asin']})"

# -------------------------------------------------------
# GOOGLE DRIVE UPLOAD
# -------------------------------------------------------
def upload_to_drive(filename, content, folder_id):
    """Upload text report to Google Drive."""
    if not drive_service:
        st.warning("⚠️ Drive upload unavailable (not configured or libraries missing)")
        return None, None
    
    try:
        file_metadata = {
            "name": filename,
            "parents": [folder_id] if folder_id else []
        }

        media = MediaIoBaseUpload(
            BytesIO(content.encode('utf-8')),
            mimetype='text/plain',
            resumable=True
        )

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        return file.get("id"), file.get("webViewLink")
    except Exception as e:
        st.error(f"Drive upload failed: {e}")
        return None, None

# -------------------------------------------------------
# DISPLAY RESULTS
# -------------------------------------------------------
def display_product(product, source):
    """Display product with Pinterest description and upload to Drive."""
    st.success(f"📡 Source: {source}")
    
    # Product title
    st.markdown(f"## {product['title']}")
    
    col1, col2 = st.columns([1, 2])

    with col1:
        # Product image
        if product["image"]:
            try:
                img_data = requests.get(product["image"], timeout=10).content
                img = Image.open(BytesIO(img_data))
                st.image(img, use_container_width=True)
            except:
                st.info("📦 Image unavailable")
        
        # Product details
        st.markdown(f"**ASIN:** `{product['asin']}`")
        st.markdown(f"**Price:** {product['price']}")
        
        # Amazon link
        st.link_button(
            "🛒 View on Amazon",
            product["link"],
            use_container_width=True,
            type="primary"
        )

    with col2:
        # Generate Pinterest description
        with st.spinner("✨ Generating Pinterest-style description..."):
            desc = generate_pinterest_description(product, all_models[model_choice])
        
        st.markdown("### 📌 Pinterest Description")
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 12px; color: white; margin: 15px 0;">
            <p style="margin: 0; font-size: 16px; line-height: 1.6;">
                {desc}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Create report
        report = f"""Amazon Product Report
======================

Title: {product['title']}
ASIN: {product['asin']}
Price: {product['price']}
Amazon Link: {product['link']}

Pinterest-Style Description:
{desc}

---
Generated by Amazon Product Finder
"""
        
        # Upload to Drive
        if drive_service:
            with st.spinner("☁️ Uploading to Google Drive..."):
                file_id, web_link = upload_to_drive(
                    f"{product['asin']}_report.txt",
                    report,
                    drive_folder_id
                )
            
            if file_id:
                st.success(f"✅ Report saved to Google Drive!")
                st.markdown(f"**File ID:** `{file_id}`")
                if web_link:
                    st.link_button("📂 Open in Drive", web_link)
        else:
            st.info("💾 Drive upload disabled. Report shown below.")
        
        # Show copyable report
        with st.expander("📄 View Full Report"):
            st.code(report)

# -------------------------------------------------------
# SEARCH BUTTON
# -------------------------------------------------------
st.markdown("---")

if st.button("🔍 Search Deliverable Product", type="primary", use_container_width=True):
    if not product_name.strip():
        st.warning("⚠️ Please enter a product name.")
    else:
        with st.spinner(f"🔍 Searching Amazon for '{product_name}'..."):
            results, source = search_amazon_fallback(product_name)
        
        if not results:
            st.error("❌ No deliverable products found. Try a different search term.")
        else:
            display_product(results[0], source)

# -------------------------------------------------------
# SIDEBAR INFO
# -------------------------------------------------------
with st.sidebar:
    st.markdown("### 📖 How It Works")
    st.markdown("""
    1. **Search** for any Amazon product
    2. **AI generates** Pinterest-style description
    3. **Auto-uploads** report to Google Drive
    4. **Get** affiliate link with your tag
    """)
    
    st.divider()
    
    st.markdown("### ⚙️ Configuration")
    st.markdown(f"**Affiliate Tag:** `{AFFILIATE_TAG}`")
    st.markdown(f"**AI Model:** {model_choice}")
    
    st.divider()
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Use specific product names
    - Check Drive folder permissions
    - Verify affiliate tag is yours
    - SerpAPI has rate limits
    """)
