import streamlit as st
import requests
import re
import json
import os
from io import BytesIO
from PIL import Image

# Google Drive (Service Account)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ----------------------------------------------------
# STREAMLIT CONFIG
# ----------------------------------------------------
st.set_page_config(page_title="🛍️ Amazon Finder + Drive Sync", layout="wide")
st.title("🛍️ Amazon Product Finder + Google Drive (Service Account)")

# ----------------------------------------------------
# SECRETS
# ----------------------------------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")

    service_account_info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
except Exception as e:
    st.error("❌ Missing secrets or invalid service account JSON.")
    st.stop()

AFFILIATE_TAG = "passionismyso-20"

# ----------------------------------------------------
# GOOGLE DRIVE (SERVICE ACCOUNT)
# ----------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES
)

drive_service = build("drive", "v3", credentials=creds)

# ----------------------------------------------------
# AI MODELS
# ----------------------------------------------------
all_models = {
    "Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "Llama 3 8B (GROQ)": "llama3-8b-8192",
    "Qwen 2.5 7B": "qwen/qwen2.5-7b-instruct",
    "Phi-3 Mini": "microsoft/phi-3-mini-128k-instruct",
}

model_choice = st.selectbox("🤖 Choose Model", list(all_models.keys()))
backup_models = st.multiselect("🛡️ Backup Models", [m for m in all_models if m != model_choice])

# ----------------------------------------------------
# PRODUCT INPUT
# ----------------------------------------------------
product_name = st.text_input("🔍 Product Name", placeholder="e.g. wireless earbuds")

# ----------------------------------------------------
# AFFILIATE TAG
# ----------------------------------------------------
def add_affiliate_tag(url):
    if "tag=" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}tag={AFFILIATE_TAG}"

# ----------------------------------------------------
# AMAZON SEARCH (SERPAPI + SCRAPER)
# ----------------------------------------------------
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
                    "title": item["title"],
                    "asin": item.get("asin"),
                    "image": item.get("thumbnail"),
                    "price": item.get("price"),
                    "link": add_affiliate_tag(item["link"])
                }]
    except:
        return []

    return []

def scrape_amazon(query):
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        page = requests.get(url, headers=headers, timeout=10).text
        asin = re.search(r'data-asin="(\w+)"', page)
        title = re.search(r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page)
        img = re.search(r'<img.*?class="s-image".*?src="(.*?)"', page)
        price = re.search(r'\$\d[\d,]*\.?\d*', page)

        if asin and title and price:
            asin_id = asin.group(1)
            link = add_affiliate_tag(f"https://www.amazon.com/dp/{asin_id}")
            return [{
                "asin": asin_id,
                "title": title.group(1),
                "image": img.group(1) if img else None,
                "price": price.group(0),
                "link": link,
            }]
    except:
        return []

    return []

def search_amazon_fallback(query):
    results = search_serpapi(query)
    if results:
        return results, "SerpAPI"

    results = scrape_amazon(query)
    if results:
        return results, "Scraper"

    return [], "No Results"

# ----------------------------------------------------
# GENERATE DESCRIPTION
# ----------------------------------------------------
def generate_description(product, model_id):
    prompt = f"""
Write a Pinterest-style product description:

Title: {product['title']}
ASIN: {product['asin']}

Rules:
- 2–3 emotional lifestyle sentences
- less than 80 words
- include emojis
"""

    if model_id == "llama3-8b-8192":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}

    try:
        r = requests.post(url, json=data, headers=headers, timeout=15)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "✨ Stylish, practical, and a must-have! ✨"

# ----------------------------------------------------
# DRIVE FILE HANDLING
# ----------------------------------------------------
def upload_or_update_file(content, filename="product_report.txt"):
    query = f"name='{filename}'"
    existing = drive_service.files().list(q=query, fields="files(id)").execute()

    # Save temporary file
    path = "/tmp/" + filename
    with open(path, "w") as f:
        f.write(content)

    media = MediaFileUpload(path, mimetype="text/plain", resumable=True)

    if existing.get("files"):
        file_id = existing["files"][0]["id"]
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        return file_id, "updated"

    file_metadata = {"name": filename}
    created = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created["id"], "created"

# ----------------------------------------------------
# DISPLAY PRODUCT
# ----------------------------------------------------
def display_product(p, origin):
    st.info(f"Found via {origin}")
    col1, col2 = st.columns([1, 2])

    with col1:
        if p["image"]:
            st.image(p["image"])
        st.markdown(f"**ASIN:** `{p['asin']}`")
        st.markdown(f"**Price:** {p['price']}")
        st.link_button("Open on Amazon", p["link"])

    with col2:
        desc = generate_description(p, all_models[model_choice])
        for b in backup_models:
            if "must-have" in desc:
                desc = generate_description(p, all_models[b])
        st.subheader("Pinterest-Style Description")
        st.write(desc)

    report = f"""
TITLE: {p['title']}
ASIN: {p['asin']}
PRICE: {p['price']}
AFFILIATE LINK: {p['link']}

--- DESCRIPTION ---

{desc}
"""

    file_id, status = upload_or_update_file(report)
    st.success(f"📄 Google Drive file {status}! (ID: {file_id})")

# ----------------------------------------------------
# SEARCH BUTTON
# ----------------------------------------------------
st.markdown("---")

if st.button("🔍 Search Deliverable Product"):
    if not product_name.strip():
        st.warning("Enter a product name first.")
    else:
        products, source = search_amazon_fallback(product_name)
        if not products:
            st.error("No products found.")
        else:
            display_product(products[0], source)
