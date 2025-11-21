import streamlit as st
import requests
from io import BytesIO
from PIL import Image

# ---------------------------------------------------------
# Streamlit Page Setup
# ---------------------------------------------------------
st.set_page_config(
    page_title="🛍️ Amazon Product Finder",
    layout="wide",
    page_icon="🛍️"
)

st.title("🛍️ Amazon Product Finder")
st.markdown("Find Amazon products with AI-generated Pinterest-style descriptions!")

# ---------------------------------------------------------
# API Keys from Secrets
# ---------------------------------------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"].strip()
    SERPAPI_KEY = st.secrets["SERPAPI_KEY"].strip()
except:
    st.error("❌ Missing API keys. Add them to Streamlit Secrets.")
    st.stop()

# ---------------------------------------------------------
# Search Input
# ---------------------------------------------------------
product_name = st.text_input(
    "🔍 Enter Product Name:",
    placeholder="e.g., wireless earbuds, yoga mat, coffee machine"
)

col1, col2 = st.columns([3, 1])
with col1:
    search_intent = st.selectbox(
        "📊 Search Intent:",
        ["Best Selling", "Highly Rated", "Budget Friendly", "Premium", "New Arrivals"]
    )
with col2:
    num_products = st.slider("Products to show:", 1, 6, 3)

# ---------------------------------------------------------
# SerpAPI Amazon Search (FIXED)
# ---------------------------------------------------------
def search_amazon_products(query, num_results, api_key):

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "amazon",
        "k": query,                 # FIXED (SerpAPI now requires "k")
        "amazon_domain": "amazon.com",
        "api_key": api_key
    }

    try:
        res = requests.get(url, params=params, timeout=20)

        if res.status_code != 200:
            return {"error": res.text}

        data = res.json()

        if "error" in data:
            return {"error": data["error"]}

        products = []
        organic = data.get("organic_results", [])

        for item in organic[:num_results]:
            if not item.get("title"):
                continue

            products.append({
                "title": item.get("title"),
                "asin": item.get("asin", "N/A"),
                "link": item.get("link", ""),
                "image": item.get("thumbnail", ""),
                "price": item.get("price", "N/A"),
                "rating": item.get("rating", "N/A"),
                "reviews": item.get("reviews_count", "N/A"),
            })

        return {"products": products}

    except Exception as e:
        return {"error": str(e)}

# ---------------------------------------------------------
# OpenRouter AI Description Generator (FIXED)
# ---------------------------------------------------------
def generate_description(title, details, api_key):

    prompt = f"""
Write a short, Pinterest-style marketing description (3–4 sentences) for:

Product: {title}
Details: {details}

Guidelines:
- Use emotional, lifestyle-influencer tone
- Use benefits more than features
- Include emojis naturally
- Maximum 100 words
"""
