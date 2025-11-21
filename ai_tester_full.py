import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from PIL import Image
import re

st.set_page_config(page_title="🛍️ Interactive Amazon Finder", layout="wide")
st.title("🛍️ Amazon Product Finder with Interactive Backup Models")

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
# Predefined text models
# -----------------------------
openrouter_models = {
    "🔥 Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "🔥 Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "🔥 Llama 3 8B (FREE)": "meta-llama/llama-3-8b-instruct:free",
    "🔥 Capybara 7B (FREE)": "nousresearch/nous-capybara-7b:free",
    "🔥 AUTO (Best free)": "openrouter/auto"
}

groq_models = {
    "⚡ Llama 3 8B (GROQ - FREE)": "llama3-8b-8192",
    "⚡ Mixtral 8x7B (GROQ - FREE)": "mixtral-8x7b-32768"
}

all_models = {**openrouter_models, **groq_models}

# -----------------------------
# Primary model selection
# -----------------------------
model_choice = st.selectbox(
    "🤖 Choose Primary Text Model:",
    list(all_models.keys())
)

# -----------------------------
# Interactive backup models table
# -----------------------------
st.markdown("### 🛡️ Backup Text Models (editable)")
# Default backup table
default_backup = pd.DataFrame(
    [(k, v) for k, v in all_models.items() if k != model_choice],
    columns=["Model Name", "Model ID"]
)
backup_table = st.data_editor(default_backup, num_rows="dynamic", use_container_width=True)

# Convert table to dictionary for lookup
backup_models_dict = {row["Model Name"]: row["Model ID"] for _, row in backup_table.iterrows()}

# -----------------------------
# Image models
# -----------------------------
image_models = {"🖼️ SD3 FREE (OpenRouter)": "stability.ai/sd3:free"}
image_model_choice = st.selectbox(
    "🖼️ Choose FREE Image Model:",
    list(image_models.keys())
)

# -----------------------------
# Product input
# -----------------------------
product_name = st.text_input("🔍 Product Name", placeholder="e.g., bluetooth speaker")

# -----------------------------
# Amazon Search Fallback
# -----------------------------
def search_serpapi(query, max_results=5):
    if not SERPAPI_KEY:
        return []
    url = "https://serpapi.com/search.json"
    params = {"engine": "amazon", "k": query, "amazon_domain": "amazon.com", "api_key": SERPAPI_KEY}
    try:
        res = requests.get(url, params=params, timeout=15).json()
        products = []
        for item in res.get("organic_results", [])[:max_results]:
            products.append({
                "title": item.get("title"),
                "asin": item.get("asin"),
                "link": item.get("link"),
                "image": item.get("thumbnail"),
                "price": item.get("price"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews_count")
            })
        return products
    except:
        return []

def scrape_amazon(query, max_results=5):
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        page = requests.get(url, headers=headers, timeout=10).text
        asins = re.findall(r'data-asin="(\w+)"', page)
        titles = re.findall(r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page)
        imgs = re.findall(r'<img.*?class="s-image".*?src="(.*?)"', page)
        results = []
        for i in range(min(max_results, len(asins))):
            results.append({
                "asin": asins[i],
                "title": titles[i] if i < len(titles) else "Unknown Product",
                "image": imgs[i] if i < len(imgs) else None,
                "link": f"https://www.amazon.com/dp/{asins[i]}"
            })
        return results
    except:
        return []

def search_amazon_with_fallback(query, max_results=5):
    results = search_serpapi(query, max_results)
    if results:
        return results, "SerpAPI 🔥"
    results = scrape_amazon(query, max_results)
    if results:
        return results, "Scraper fallback 🖇️"
    return [], "No source found"

# -----------------------------
# AI Description & Image
# -----------------------------
def generate_description(product, model_id):
    prompt = f"""
Write a Pinterest-style marketing description (3-4 sentences)
for this Amazon product:

Title: {product['title']}
ASIN: {product['asin']}

Make it emotional, lifestyle-style, under 80 words with a few emojis.
"""
    if model_id in groq_models.values():
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data = {"model": model_id, "messages": [{"role": "user", "content": prompt}]}

    try:
        r = requests.post(url, json=data, headers=headers)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "🌟 Beautiful product loved by shoppers!"

def generate_image(prompt):
    model = image_models[image_model_choice]
    url = "https://openrouter.ai/api/v1/images"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    data = {"model": model, "prompt": prompt}
    try:
        r = requests.post(url, json=data, headers=headers)
        img_bytes = BytesIO(requests.get(r.json()["data"][0]["url"]).content)
        return Image.open(img_bytes)
    except:
        return None

# -----------------------------
# Display products
# -----------------------------
def display_products(products, source_name="Unknown"):
    st.info(f"Results from: {source_name}")
    for p in products:
        st.subheader(p["title"])
        col1, col2 = st.columns([1, 2])
        with col1:
            if p.get("image"):
                st.image(p["image"])
            st.link_button("Open on Amazon", p["link"])
        with col2:
            # Try primary model
            model_id = all_models[model_choice]
            desc = generate_description(p, model_id)
            # Try backup models from interactive table if primary fails
            for backup_name, backup_id in backup_models_dict.items():
                if not desc or "Beautiful product" in desc:
                    desc = generate_description(p, backup_id)
            st.write(desc)
            img = generate_image(desc)
            if img:
                st.image(img)
        st.divider()

# -----------------------------
# Search button at bottom
# -----------------------------
st.markdown("---")
if st.button("🔍 Search Amazon (FREE)"):
    if not product_name.strip():
        st.warning("Type a product name first.")
    else:
        products, source_name = search_amazon_with_fallback(product_name)
        if not products:
            st.error("No results found on any source.")
        else:
            display_products(products, source_name)
