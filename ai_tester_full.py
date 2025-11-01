import time
import datetime
import requests
import streamlit as st
from io import BytesIO
from PIL import Image

# -----------------------------
# 🔑 Load API Keys from Streamlit Secrets
# -----------------------------
openrouter_key = st.secrets["OPENROUTER_API_KEY"]
serpapi_key = st.secrets["SERPAPI_KEY"]

# -----------------------------
# 🧠 Streamlit Page Config
# -----------------------------
st.set_page_config(page_title="🧠 AI + 🖼️ Image Generator", layout="wide")

st.title("🧠 AI Text & 🖼️ Image Generator")
st.markdown("Enter a single prompt — get **AI-generated text** and **related images** instantly!")

# -----------------------------
# 🚫 Stop if API keys missing
# -----------------------------
if not openrouter_key or not serpapi_key:
    st.error("❌ Missing API keys. Please add them in Streamlit Secrets.")
    st.stop()

# -----------------------------
# 🧩 Helper Functions
# -----------------------------
@st.cache_data(ttl=3600)
def fetch_models(api_key):
    """Fetch available models from OpenRouter"""
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        return sorted([m["id"] for m in data["data"]])
    else:
        st.error(f"❌ Could not fetch models: {res.text}")
        return []

def call_model(model, prompt):
    """Generate text via OpenRouter"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json"
    }
    data = {"model": model, "messages": [{"role": "user", "content": prompt}]}

    start = time.time()
    response = requests.post(url, headers=headers, json=data)
    end = time.time()

    if response.status_code != 200:
        return {"error": response.text, "time": round(end - start, 2)}

    res = response.json()
    text = res["choices"][0]["message"]["content"]
    tokens = res.get("usage", {}).get("total_tokens", "N/A")
    return {"text": text, "tokens": tokens, "time": round(end - start, 2)}

def search_images(query, num_results=3):
    """Search Google Images via SerpAPI"""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "tbm": "isch",
        "num": num_results,
        "api_key": serpapi_key
    }
    res = requests.get(url, params=params)
    if res.status_code != 200:
        st.error(f"❌ Image search failed: {res.text}")
        return []
    data = res.json()
    return [img["original"] for img in data.get("images_results", [])[:num_results]]

# -----------------------------
# 🧠 UI Components
# -----------------------------
models_list = fetch_models(openrouter_key)
if not models_list:
    st.stop()

prompt = st.text_area(
    "📝 Enter your prompt:",
    height=150,
    placeholder="e.g. A serene landscape with AI explaining the beauty of nature..."
)

selected_model = st.selectbox("🤖 Select a model:", models_list, index=0)
num_images = st.slider("🖼️ Number of images:", 1, 6, 3)

# -----------------------------
# 🚀 Generate Button
# -----------------------------
if st.button("🚀 Generate Text + Images"):
    if not prompt.strip():
        st.warning("Please enter a prompt.")
        st.stop()

    # --- Generate AI Text ---
    with st.spinner("🧠 Generating text from model..."):
        text_result = call_model(selected_model, prompt)

    if "error" in text_result:
        st.error(text_result["error"])
        st.stop()

    st.subheader("🧠 AI Response")
    st.info(f"⏱️ {text_result['time']} sec | 🧮 Tokens: {text_result['tokens']}")
    st.write(text_result["text"])

    # --- Search Related Images ---
    with st.spinner("🔍 Searching related images..."):
        images = search_images(prompt, num_images)

    if images:
        st.subheader("🖼️ Related Images")
        cols = st.columns(len(images))
        for i, (col, url) in enumerate(zip(cols, images), 1):
            try:
                img_data = requests.get(url).content
                img = Image.open(BytesIO(img_data))
                col.image(img, caption=f"Image {i}", use_container_width=True)
                col.download_button(
                    label="⬇️ Download",
                    data=img_data,
                    file_name=f"image_{i}.jpg",
                    mime="image/jpeg",
                )
            except Exception as e:
                col.error(f"⚠️ Could not load image {i}: {e}")
    else:
        st.error("❌ No images found.")
