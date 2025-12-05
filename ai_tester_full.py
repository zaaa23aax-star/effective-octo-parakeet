import streamlit as st
import requests
import json
from io import BytesIO
from PIL import Image
import re

# ================================================================
# PAGE CONFIG
# ================================================================
st.set_page_config(page_title="🛍️ Amazon Finder", layout="wide")
st.title("🛍️ Amazon Product Finder - Drive Optional Version")

# ================================================================
# SAFE GOOGLE IMPORTS (App will NOT crash if missing)
# ================================================================
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_ENABLED = True
except Exception:
    GOOGLE_ENABLED = False

# ================================================================
# LOAD API KEYS
# ================================================================
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
except:
    st.error("❌ Missing API keys in Streamlit Secrets.")
    st.stop()

AFFILIATE_TAG = "passionismyso-20"

# ================================================================
# LOAD GOOGLE DRIVE SERVICE (Optional)
# ================================================================
def load_drive_service():
    if not GOOGLE_ENABLED:
        return None

    if "google_service_account" not in st.secrets:
        return None

    try:
        sa_info = json.loads(st.secrets["google_service_account"])
        creds = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        st.warning(f"⚠️ Google Drive disabled: {e}")
        return None

drive_service = load_drive_service()

# ================================================================
# TEXT MODEL OPTIONS
# ================================================================
all_models = {
    "🔥 Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "🔥 Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "⚡ Llama 3 8B (GROQ - FREE)": "llama3-8b-8192",
}

model_choice = st.selectbox("🤖 Choose Primary Model:", list(all_models.keys()))

backup_models = st.multiselect(
    "🛡️ Backup Models (if primary fails):",
    [k for k in all_models.keys() if k != model_choice]
)

# ================================================================
# PRODUCT INPUT
# ================================================================
product_name = st.text_input("🔍 Product Name", placeholder="e.g., wireless headphones")

# ================================================================
# ADD AFFILIATE TAG TO AMAZON LINKS
# ================================================================
def add_affiliate_tag(link):
    if "tag=" in link:
        return link  # already tagged

    separator = "&" if "?" in link else "?"
    return f"{link}{separator}tag={AFFILIATE_TAG}"

# ================================================================
# AMAZON SEARCH
# ================================================================
def search_serpapi(query):
    if not SERPAPI_KEY:
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "amazon",
        "k": query,
        "amazon_domain": "amazon.com",
        "api_key": SERPAPI_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=15).json()
        for item in res.get("organic_results", []):
            if item.get("link") and item.get("price"):
                return [{
                    "title": item.get("title"),
                    "asin": item.get("asin"),
                    "image": item.get("thumbnail"),
                    "link": add_affiliate_tag(item.get("link")),
                    "price": item.get("price")
                }]
    except:
        pass

    return []

def scrape_amazon(query):
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        page = requests.get(url, headers=headers, timeout=10).text
        asin_match = re.search(r'data-asin="(\w+)"', page)
        title_match = re.search(r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page)
        img_match = re.search(r'<img.*?class="s-image".*?src="(.*?)"', page)
        price_match = re.search(r'\$\d[\d,]*\.?\d*', page)

        if asin_match and title_match and price_match:
            link = f"https://www.amazon.com/dp/{asin_match.group(1)}"
            return [{
                "asin": asin_match.group(1),
                "title": title_match.group(1),
                "image": img_match.group(1),
                "link": add_affiliate_tag(link),
                "price": price_match.group(0)
            }]
    except:
        pass

    return []

def search_amazon_fallback(query):
    r = search_serpapi(query)
    if r:
        return r, "SerpAPI 🔥"

    r = scrape_amazon(query)
    if r:
        return r, "Scraper Fallback 🖇️"

    return [], "No deliverable product found"

# ================================================================
# PINTEREST DESCRIPTION
# ================================================================
def generate_pinterest_description(product, model_id):
    prompt = f"""
Create a short Pinterest-style description (<80 words):

Title: {product['title']}
ASIN: {product['asin']}

Use lifestyle language and emojis. Make it desirable.
"""

    if model_id == "llama3-8b-8192":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}

    try:
        r = requests.post(url, json=data, headers=headers, timeout=20)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return f"✨ {product['title']} is a must-have! 🌟"

# ================================================================
# GOOGLE DRIVE UPLOAD (OPTIONAL)
# ================================================================
def upload_to_drive(filename, content):
    if not drive_service:
        return None

    try:
        file_metadata = {"name": filename}
        media = bytes(content, "utf-8")

        file = drive_service.files().create(
            body=file_metadata,
            media_body=BytesIO(media),
            fields="id"
        ).execute()

        return file.get("id")
    except Exception as e:
        st.warning(f"⚠️ Upload failed: {e}")
        return None

# ================================================================
# DISPLAY PRODUCT
# ================================================================
def display_product(product, source_name="Unknown"):
    st.info(f"Results from: {source_name}")
    st.subheader(product["title"])

    col1, col2 = st.columns([1, 2])

    with col1:
        if product.get("image"):
            st.image(product["image"])

        st.markdown(f"**ASIN:** `{product['asin']}`")
        st.markdown(f"**Price:** {product['price']}")
        st.link_button("Open on Amazon", product["link"])

    with col2:
        desc = generate_pinterest_description(product, all_models[model_choice])

        for backup in backup_models:
            if not desc or "must-have" in desc:
                desc = generate_pinterest_description(product, all_models[backup])

        st.markdown(f"### Pinterest Description")
        st.write(desc)

        report_text = (
            f"Product: {product['title']}\n\n"
            f"ASIN: {product['asin']}\n"
            f"Price: {product['price']}\n"
            f"Link: {product['link']}\n\n"
            f"Description:\n{desc}"
        )

        st.markdown("---")
        st.subheader("📄 Report")

        st.download_button("Download Report", report_text, file_name="product_report.txt")

        if drive_service:
            file_id = upload_to_drive("product_report.txt", report_text)
            if file_id:
                st.success("Uploaded to Google Drive successfully!")
            else:
                st.warning("Drive upload failed. You can still download the report.")

# ================================================================
# SEARCH BUTTON
# ================================================================
st.markdown("---")
if st.button("🔍 Search Deliverable Product"):
    if not product_name.strip():
        st.warning("Type a product name first.")
    else:
        products, source_name = search_amazon_fallback(product_name)
        if not products:
            st.error("No deliverable products found.")
        else:
            display_product(products[0], source_name)
