import streamlit as st
import requests
import pandas as pd
import time
import datetime
from io import BytesIO
from PIL import Image
import os

# -----------------------------
# Streamlit Page Setup
# -----------------------------
st.set_page_config(page_title="🧠 AI Model & Image Tester", layout="wide")

st.title("🧠 OpenRouter AI & 🔍 Image Search App")
st.markdown("Test OpenRouter models and search images from Google via SerpAPI — all in one place!")

# -----------------------------
# Sidebar Inputs
# -----------------------------
st.sidebar.header("🔑 API Keys")
openrouter_key = st.sidebar.text_input("OpenRouter API Key:", type="password")
serpapi_key = st.sidebar.text_input("SerpAPI Key:", type="password")

st.sidebar.markdown("[Get OpenRouter Key](https://openrouter.ai/keys)")
st.sidebar.markdown("[Get SerpAPI Key](https://serpapi.com/manage-api-key)")

tab1, tab2 = st.tabs(["🤖 Model Tester", "🖼️ Image Search"])

# ==============================================================
# 🧠 TAB 1: OPENROUTER MODEL TESTER
# ==============================================================
with tab1:
    if not openrouter_key:
        st.warning("Please enter your OpenRouter API key in the sidebar.")
        st.stop()

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

    models_list = fetch_models(openrouter_key)
    if not models_list:
        st.stop()

    prompt = st.text_area("📝 Enter your prompt:", height=150, placeholder="e.g. Explain quantum computing in simple terms...")
    selected_models = st.multiselect(
        "🤖 Select models to test (type to search):",
        options=models_list,
        default=[models_list[0]] if models_list else [],
    )

    if "runs" not in st.session_state:
        st.session_state["runs"] = []

    def call_model(model, prompt):
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"}
        data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        start = time.time()
        response = requests.post(url, headers=headers, json=data)
        end = time.time()

        if response.status_code != 200:
            return {"model": model, "error": response.text, "time": round(end - start, 2)}

        res = response.json()
        text = res["choices"][0]["message"]["content"]
        tokens = res.get("usage", {}).get("total_tokens", "N/A")
        return {"model": model, "text": text, "tokens": tokens, "time": round(end - start, 2)}

    if st.button("🚀 Run Test"):
        if not prompt.strip():
            st.warning("Please enter a prompt.")
        elif not selected_models:
            st.warning("Please select at least one model.")
        else:
            results = []
            for model in selected_models:
                with st.spinner(f"Querying {model}..."):
                    res = call_model(model, prompt)
                    results.append(res)
            st.session_state["runs"].append(
                {
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "prompt": prompt,
                    "results": results,
                }
            )
            st.success("✅ Done!")

    # Display previous runs
    for run in reversed(st.session_state["runs"][-3:]):
        st.markdown(f"### 🧾 Test from {run['timestamp']}")
        st.write(f"**Prompt:** {run['prompt']}")
        df = pd.DataFrame(run["results"])
        st.dataframe(df)
        for res in run["results"]:
            st.markdown(f"#### {res['model']}")
            if "error" in res:
                st.error(res["error"])
            else:
                st.info(f"⏱️ {res['time']} sec | 🧮 Tokens: {res['tokens']}")
                st.write(res["text"])

# ==============================================================
# 🖼️ TAB 2: IMAGE SEARCH (SerpAPI)
# ==============================================================
with tab2:
    st.subheader("🖼️ Google Image Search via SerpAPI")

    if not serpapi_key:
        st.warning("Please enter your SerpAPI key in the sidebar.")
        st.stop()

    query = st.text_input("🔍 Describe the image you want to search for:", placeholder="e.g. sunset over mountains")
    num_results = st.slider("Number of images to show:", 1, 10, 5)

    def search_images(query, num_results=5):
        url = "https://serpapi.com/search.json"
        params = {"engine": "google", "q": query, "tbm": "isch", "num": num_results, "api_key": serpapi_key}
        res = requests.get(url, params=params)
        if res.status_code != 200:
            st.error(f"❌ Search failed: {res.text}")
            return []
        data = res.json()
        return [img["original"] for img in data.get("images_results", [])[:num_results]]

    if st.button("🔎 Search Images"):
        if not query.strip():
            st.warning("Please enter a search query.")
        else:
            with st.spinner("Searching images..."):
                image_urls = search_images(query, num_results)
            if image_urls:
                cols = st.columns(len(image_urls))
                for i, (col, url) in enumerate(zip(cols, image_urls), 1):
                    try:
                        img_data = requests.get(url).content
                        img = Image.open(BytesIO(img_data))
                        col.image(img, caption=f"Result {i}", use_container_width=True)
                        if col.download_button(
                            label="⬇️ Download",
                            data=img_data,
                            file_name=f"image_{i}.jpg",
                            mime="image/jpeg",
                        ):
                            st.success(f"✅ Image {i} downloaded.")
                    except Exception as e:
                        st.error(f"⚠️ Could not load image {i}: {e}")
            else:
                st.error("❌ No images found.")
