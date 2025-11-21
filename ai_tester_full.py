import streamlit as st
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

# ---------------------------------------------------------
# STREAMLIT SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="🛍️ Amazon Product Finder (FREE)", layout="wide")

st.title("🛍️ 100% FREE Amazon Product Finder")
st.markdown("Find products + AI descriptions using **only free models** (OpenRouter + Groq).")

# ---------------------------------------------------------
# API KEYS
# ---------------------------------------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("❌ Add OPENROUTER_API_KEY and GROQ_API_KEY to Streamlit secrets.")
    st.stop()

# ---------------------------------------------------------
# FREE MODEL LISTS
# ---------------------------------------------------------
openrouter_free_models = {
    "🔥 Mixtral 8x7B (FREE)": "mistralai/mixtral-8x7b-instruct:free",
    "🔥 Mistral 7B (FREE)": "mistralai/mistral-7b-instruct:free",
    "🔥 Llama 3 8B (FREE)": "meta-llama/llama-3-8b-instruct:free",
    "🔥 Capybara 7B (FREE)": "nousresearch/nous-capybara-7b:free",
    "🔥 AUTO (Best free)": "openrouter/auto"
}

groq_free_models = {
    "⚡ Llama 3 8B (GROQ - FREE)": "llama3-8b-8192",
    "⚡ Mixtral 8x7B (GROQ - FREE)": "mixtral-8x7b-32768"
}

image_models = {
    "🖼️ SD3 FREE (OpenRouter)": "stability.ai/sd3:free"
}

# ---------------------------------------------------------
# UI INPUTS
# ---------------------------------------------------------
product_name = st.text_input("🔍 Product Name", placeholder="e.g. bluetooth speaker")

model_choice = st.selectbox(
    "🤖 Choose AI Model",
    list(openrouter_free_models.keys()) + list(groq_free_models.keys())
)

image_model_choice = st.selectbox(
    "🖼️ Choose FREE Image Model",
    list(image_models.keys())
)

# ---------------------------------------------------------
# FREE AMAZON SCRAPER (no SerpAPI)
# ---------------------------------------------------------
def scrape_amazon(query, max_results=5):
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        page = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(page.text, "html.parser")

        results = []
        items = soup.select("div[data-asin]")[:max_results]

        for item in items:
            asin = item["data-asin"]
            if not asin:
                continue

            title = item.select_one("h2 span")
            img = item.select_one("img.s-image")

            results.append({
                "title": title.text.strip() if title else "Unknown product",
                "asin": asin,
                "image": img["src"] if img else None,
                "link": f"https://www.amazon.com/dp/{asin}"
            })
        return results

    except:
        return []

# ---------------------------------------------------------
# AI DESCRIPTION GENERATOR
# ---------------------------------------------------------
def generate_description(product, model_id):
    prompt = f"""
Write a Pinterest-style marketing description (3–4 sentences)
for this Amazon product:

Title: {product['title']}
ASIN: {product['asin']}

Keep it emotional, aesthetic, lifestyle-influencer style.
Under 80 words. Include a few emojis.
"""

    # GROQ
    if model_id in groq_free_models.values():
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        data = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

    # OPENROUTER
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://streamlit-app",
            "Content-Type": "application/json"
        }
        data = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}]
        }

    try:
        r = requests.post(url, json=data, headers=headers)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "🌟 Beautiful product loved by shoppers!"

# ---------------------------------------------------------
# IMAGE GENERATION (FREE)
# ---------------------------------------------------------
def generate_image(prompt):
    model = image_models[image_model_choice]

    url = "https://openrouter.ai/api/v1/images"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "prompt": prompt
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        img_bytes = BytesIO(requests.get(r.json()["data"][0]["url"]).content)
        return Image.open(img_bytes)
    except:
        return None

# ---------------------------------------------------------
# SEARCH BUTTON
# ---------------------------------------------------------
if st.button("🔍 Search Amazon (FREE)"):
    if not product_name.strip():
        st.warning("Please type a product name.")
        st.stop()

    products = scrape_amazon(product_name)

    if not products:
        st.error("No results found.")
        st.stop()

    for p in products:
        st.subheader(p["title"])

        col1, col2 = st.columns([1, 2])

        with col1:
            if p["image"]:
                st.image(p["image"])
            st.link_button("Open on Amazon", p["link"])

        with col2:
            with st.spinner("✨ Writing description..."):
                model_id = (
                    openrouter_free_models[model_choice]
                    if model_choice in openrouter_free_models
                    else groq_free_models[model_choice]
                )
                desc = generate_description(p, model_id)
                st.write(desc)

            with st.spinner("🎨 Generating Pinterest image..."):
                img = generate_image(desc)
                if img:
                    st.image(img)
                else:
                    st.info("Image model unavailable right now.")

        st.divider()
