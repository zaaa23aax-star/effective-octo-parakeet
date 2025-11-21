import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import re

st.set_page_config(page_title="🛍️ Amazon Finder (Deliverable)", layout="wide")
st.title("🛍️ Amazon Product Finder - Pinterest Style (Deliverable Only)")

# -----------------------------
# API keys
# -----------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
except:
    st.error("❌ Add OpenRouter, Groq, and SerpAPI keys in Streamlit secrets.")
    st.stop()

# -----------------------------
# Text models
# -----------------------------
all_models = {
    "🔥 Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "🔥 Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "⚡ Llama 3 8B (GROQ - FREE)": "llama3-8b-8192"
}

model_choice = st.selectbox("🤖 Choose Primary Text Model:", list(all_models.keys()))
backup_models = st.multiselect(
    "🛡️ Backup Models (if primary fails):",
    [k for k in all_models.keys() if k != model_choice]
)

# -----------------------------
# Product input
# -----------------------------
product_name = st.text_input("🔍 Product Name", placeholder="e.g., wireless headphones")

# -----------------------------
# Amazon search (1 product only)
# -----------------------------
def search_serpapi(query):
    if not SERPAPI_KEY:
        return []
    url = "https://serpapi.com/search.json"
    params = {"engine": "amazon", "k": query, "amazon_domain": "amazon.com", "api_key": SERPAPI_KEY}
    try:
        res = requests.get(url, params=params, timeout=15).json()
        for item in res.get("organic_results", []):
            # Check if deliverable: valid link and has price
            if item.get("link") and "amazon.com" in item["link"] and item.get("price"):
                return [{
                    "title": item.get("title"),
                    "asin": item.get("asin"),
                    "link": item.get("link"),
                    "image": item.get("thumbnail"),
                    "price": item.get("price")
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
        title_match = re.search(r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page)
        img_match = re.search(r'<img.*?class="s-image".*?src="(.*?)"', page)
        price_match = re.search(r'\$\d[\d,]*\.?\d*', page)  # crude price check
        if asin_match and title_match and price_match:
            return [{
                "asin": asin_match.group(1),
                "title": title_match.group(1),
                "image": img_match.group(1) if img_match else None,
                "link": f"https://www.amazon.com/dp/{asin_match.group(1)}",
                "price": price_match.group(0)
            }]
        return []
    except:
        return []

def search_amazon_fallback(query):
    results = search_serpapi(query)
    if results:
        return results, "SerpAPI 🔥"
    results = scrape_amazon(query)
    if results:
        return results, "Scraper fallback 🖇️"
    return [], "No deliverable product found"

# -----------------------------
# Pinterest-style description
# -----------------------------
def generate_pinterest_description(product, model_id):
    prompt = f"""
Create a Pinterest-style marketing description for this Amazon product:

Title: {product['title']}
ASIN: {product['asin']}

Write 2-3 short, engaging sentences:
- Use emotional, lifestyle language
- Highlight benefits, not just features
- Include relevant emojis naturally
- Make readers want to click and buy
- Keep it under 80 words
"""
    if model_id in ["llama3-8b-8192"]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=20)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return f"✨ {product['title']} is a must-have! ASIN: {product['asin']} 🌟"

# -----------------------------
# Display product
# -----------------------------
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
        st.markdown(f"**Pinterest-Style Description:** {desc}")

# -----------------------------
# Search button
# -----------------------------
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
