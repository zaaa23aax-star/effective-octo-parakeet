import streamlit as st
import requests
import pandas as pd
import time
import datetime
from io import BytesIO
from PIL import Image

# -----------------------------
# Streamlit Setup
# -----------------------------
st.set_page_config(page_title="🧠 AI + 🖼️ Image Generator", layout="wide")
st.title("🧠 AI Text & 🖼️ Image Generator")
st.markdown("Enter a prompt once — get both **AI-generated text** and **related images** instantly!")

# -----------------------------
# API Keys (from Streamlit Secrets)
# -----------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
except Exception as e:
    st.error("❌ Missing API keys in Streamlit Secrets. Please add them in your app settings.")
    st.stop()

# -----------------------------
# Load Models
# -----------------------------
@st.cache_data(ttl=3600)
def fetch_models(api_key):
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        return sorted([m["id"] for m in data["data"]])
    else:
        st.error(f"❌ Could not fetch models: {res.text}")
        return []

models_list = fetch_models(OPENROUTER_API_KEY)
if not models_list:
    st.stop()

# -----------------------------
# User Input
# -----------------------------
prompt = st.text_area(
    "📝 Enter your prompt:",
    height=150,
    placeholder="e.g. A serene landscape with AI explaining the beauty of nature...",
)
selected_model = st.selectbox("🤖 Select a model to use:", models_list, index=0)
num_images = st.slider("🖼️ Number of images:", 1, 6, 3)

# -----------------------------
# Core Functions
# -----------------------------
def call_model(model, prompt):
    """Query OpenRouter for text output."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-streamlit-app-url",  # optional but good practice
        "X-Title": "AI Image + Text App"  # optional metadata
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
    """Search Google Images using SerpAPI."""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "tbm": "isch",
        "num": num_results,
        "api_key": SERPAPI_KEY
    }
    res = requests.get(url, params=params)
    if res.status_code != 200:
        st.error(f"❌ Image search failed: {res.text}")
        return []
    data = res.json()
    return [img["original"] for img in data.get("images_results", [])[:num_results]]

# -----------------------------
# Run Button
# -----------------------------
if st.button("🚀 Generate Text + Images"):
    if not prompt.strip():
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Generating AI text..."):
            text_result = call_model(selected_model, prompt)

        if "error" in text_result:
            st.error(text_result["error"])
        else:
            st.subheader("🧠 AI Response")
            st.info(f"⏱️ {text_result['time']} sec | 🧮 Tokens: {text_result['tokens']}")
            st.write(text_result["text"])

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
