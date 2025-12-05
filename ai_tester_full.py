import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import re
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# -------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------
st.set_page_config(page_title="Amazon Finder - Deliverable", layout="wide")
st.title("🛍️ Amazon Product Finder - Pinterest Style + Auto Drive Upload")

# -------------------------------------------------------
# LOAD SECRETS (API KEYS + DRIVE)
# -------------------------------------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
    SERVICE_ACCOUNT_JSON = st.secrets["SERVICE_ACCOUNT_JSON"]
except:
    st.error("❌ Missing Streamlit secrets. Add API keys + SERVICE_ACCOUNT_JSON.")
    st.stop()

# -------------------------------------------------------
# GOOGLE DRIVE SERVICE ACCOUNT LOGIN
# -------------------------------------------------------
try:
    service_info = json.loads(SERVICE_ACCOUNT_JSON)

    creds = service_account.Credentials.from_service_account_info(
        service_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )

    drive_service = build("drive", "v3", credentials=creds)
except Exception as e:
    st.error(f"Google Drive auth failed: {e}")
    st.stop()

# -------------------------------------------------------
# AMAZON AFFILIATE TAG
# -------------------------------------------------------
AFFILIATE_TAG = "passionismyso-20"

def add_affiliate_tag(link):
    if "tag=" in link:
        return link
    if "?" in link:
        return link + f"&tag={AFFILIATE_TAG}"
    else:
        return link + f"?tag={AFFILIATE_TAG}"

# -------------------------------------------------------
# TEXT MODELS
# -------------------------------------------------------
all_models = {
    "🔸 Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "🔸 Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "⚡ Llama 3 8B (Groq)": "llama3-8b-8192",
    "✨ Llama 3 70B": "meta-llama/llama-3-70b-instruct",
    "✨ Qwen 2.5 32B": "qwen/qwen2.5-32b-instruct"
}

model_choice = st.selectbox("🤖 Choose AI Model", list(all_models.keys()))

# -------------------------------------------------------
# PRODUCT INPUT
# -------------------------------------------------------
product_name = st.text_input("🔍 Product Name", placeholder="e.g. wireless headphones")

# -------------------------------------------------------
# AMAZON SEARCH FUNCTIONS
# -------------------------------------------------------
def search_serpapi(query):
    if not SERPAPI_KEY:
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "amazon",
        "k": query,
        "amazon_domain": "amazon.com",
        "api_key": SERPAPI_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=15).json()
        for item in res.get("organic_results", []):
            if item.get("link") and "amazon.com" in item["link"] and item.get("price"):
                return [{
                    "title": item["title"],
                    "asin": item.get("asin"),
                    "link": add_affiliate_tag(item["link"]),
                    "image": item.get("thumbnail"),
                    "price": item.get("price"),
                }]
        return []
    except:
        return []


def scrape_amazon(query):
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        page = requests.get(url, headers=headers, timeout=10).text

        asin_match = re.search(r'data-asin="(\w+)"', page)
        title_match = re.search(
            r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page
        )
        img_match = re.search(r'<img.*?class="s-image".*?src="(.*?)"', page)
        price_match = re.search(r'\$\d[\d,]*\.?\d*', page)

        if asin_match and title_match and price_match:
            link = f"https://www.amazon.com/dp/{asin_match.group(1)}"
            link = add_affiliate_tag(link)

            return [{
                "asin": asin_match.group(1),
                "title": title_match.group(1),
                "image": img_match.group(1) if img_match else None,
                "link": link,
                "price": price_match.group(0)
            }]
        return []
    except:
        return []


def search_amazon_fallback(query):
    r1 = search_serpapi(query)
    if r1:
        return r1, "SerpAPI 🔥"

    r2 = scrape_amazon(query)
    if r2:
        return r2, "Scraper Fallback 🖇️"

    return [], "❌ Nothing Found"

# -------------------------------------------------------
# PINTEREST DESCRIPTION VIA AI
# -------------------------------------------------------
def generate_pinterest_description(product, model_id):
    prompt = f"""
Write a short Pinterest-style promotional description (max 80 words).

Product:
Title: {product["title"]}
ASIN: {product["asin"]}

Tone:
• Emotional + lifestyle
• Benefits > features
• Add emojis naturally
"""

    if model_id == "llama3-8b-8192":  # Groq backend
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                   "Content-Type": "application/json"}

    data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}

    try:
        r = requests.post(url, json=data, headers=headers, timeout=20)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return f"{product['title']} — a must-have! (ASIN: {product['asin']})"

# -------------------------------------------------------
# GOOGLE DRIVE UPLOAD
# -------------------------------------------------------
def upload_to_drive(filename, content):
    file_metadata = {
        "name": filename,
        "parents": ["1XAJLIDBpWPYk6-xzGahLfdU4cqzkF7Bc"]  # your chosen folder
    }

    media = {
        "mimeType": "text/plain",
        "body": content
    }

    file = drive_service.files().create(
        body=file_metadata,
        media_body=BytesIO(content.encode()),
        fields="id"
    ).execute()

    return file.get("id")

# -------------------------------------------------------
# DISPLAY RESULTS
# -------------------------------------------------------
def display_product(product, source):
    st.info(f"📡 Source: {source}")
    st.subheader(product["title"])

    col1, col2 = st.columns([1, 2])

    with col1:
        if product["image"]:
            st.image(product["image"])
        st.markdown(f"**ASIN:** `{product['asin']}`")
        st.markdown(f"**Price:** {product['price']}")
        st.link_button("Open on Amazon", product["link"])

    with col2:
        desc = generate_pinterest_description(product, all_models[model_choice])
        st.markdown("### ✨ Pinterest Description")
        st.write(desc)

        report = f"""
Product Report
--------------
Title: {product['title']}
ASIN: {product['asin']}
Price: {product['price']}
Link: {product['link']}

Description:
{desc}
"""
        file_id = upload_to_drive(f"{product['asin']}_report.txt", report)
        st.success(f"Report saved to Drive (ID: {file_id})")

# -------------------------------------------------------
# SEARCH BUTTON
# -------------------------------------------------------
st.markdown("---")

if st.button("🔍 Search Deliverable Product"):
    if not product_name.strip():
        st.warning("Please enter a product name.")
    else:
        results, source = search_amazon_fallback(product_name)
        if not results:
            st.error("No deliverable products found.")
        else:
            display_product(results[0], source)
