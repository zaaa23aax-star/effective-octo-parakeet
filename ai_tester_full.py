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
except KeyError as e:
    st.error(f"❌ Missing API key in Streamlit Secrets: {e}")
    st.info("""
    **How to fix this:**
    1. Go to your Streamlit Cloud dashboard
    2. Click on your app → Settings → Secrets
    3. Add the following format:
    ```
    OPENROUTER_API_KEY = "your-openrouter-key-here"
    SERPAPI_KEY = "your-serpapi-key-here"
    ```
    4. Save and reboot the app
    """)
    st.stop()
except Exception as e:
    st.error(f"❌ Error loading secrets: {e}")
    st.stop()

# Validate API keys are not empty
if not OPENROUTER_API_KEY or not SERPAPI_KEY:
    st.error("❌ API keys are empty. Please configure them in Streamlit Secrets.")
    st.stop()

# -----------------------------
# Load Models
# -----------------------------
@st.cache_data(ttl=3600)
def fetch_models(api_key):
    """Fetch available models from OpenRouter."""
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://streamlit-app",
        "X-Title": "Streamlit AI App"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return sorted([m["id"] for m in data.get("data", [])])
        else:
            st.error(f"❌ Could not fetch models (Status {res.status_code}): {res.text}")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Network error fetching models: {e}")
        return []

with st.spinner("Loading available models..."):
    models_list = fetch_models(OPENROUTER_API_KEY)

if not models_list:
    st.error("❌ No models available. Please check your OPENROUTER_API_KEY.")
    st.stop()

# -----------------------------
# User Input
# -----------------------------
prompt = st.text_area(
    "📝 Enter your prompt:",
    height=150,
    placeholder="e.g. A serene landscape with AI explaining the beauty of nature...",
)

selected_model = st.selectbox(
    "🤖 Select a model to use:", 
    models_list, 
    index=0 if models_list else None
)

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
        "HTTP-Referer": "https://streamlit-app",
        "X-Title": "AI Image + Text App"
    }
    data = {
        "model": model, 
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=60)
        end = time.time()

        if response.status_code != 200:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except:
                pass
            return {"error": f"Status {response.status_code}: {error_msg}", "time": round(end - start, 2)}

        res = response.json()
        text = res["choices"][0]["message"]["content"]
        tokens = res.get("usage", {}).get("total_tokens", "N/A")
        return {"text": text, "tokens": tokens, "time": round(end - start, 2)}
    
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Please try again."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}

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
    
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            st.error(f"❌ Image search failed (Status {res.status_code}): {res.text}")
            return []
        
        data = res.json()
        images = data.get("images_results", [])
        return [img["original"] for img in images[:num_results] if "original" in img]
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Network error during image search: {e}")
        return []
    except Exception as e:
        st.error(f"❌ Error processing images: {e}")
        return []

# -----------------------------
# Run Button
# -----------------------------
if st.button("🚀 Generate Text + Images", type="primary"):
    if not prompt.strip():
        st.warning("⚠️ Please enter a prompt.")
    else:
        # Generate AI Text
        with st.spinner("🧠 Generating AI text..."):
            text_result = call_model(selected_model, prompt)

        if "error" in text_result:
            st.error(f"❌ AI Generation Error: {text_result['error']}")
        else:
            st.subheader("🧠 AI Response")
            st.info(f"⏱️ {text_result['time']} sec | 🧮 Tokens: {text_result['tokens']}")
            st.write(text_result["text"])

            # Search Images
            with st.spinner("🔍 Searching related images..."):
                images = search_images(prompt, num_images)

            if images:
                st.subheader("🖼️ Related Images")
                cols = st.columns(min(len(images), 3))  # Max 3 columns
                
                for i, url in enumerate(images):
                    col = cols[i % len(cols)]
                    try:
                        img_response = requests.get(url, timeout=10)
                        img_response.raise_for_status()
                        img_data = img_response.content
                        img = Image.open(BytesIO(img_data))
                        
                        col.image(img, caption=f"Image {i+1}", use_container_width=True)
                        col.download_button(
                            label="⬇️ Download",
                            data=img_data,
                            file_name=f"image_{i+1}.jpg",
                            mime="image/jpeg",
                            key=f"download_{i}"
                        )
                    except Exception as e:
                        col.error(f"⚠️ Could not load image {i+1}")
                        col.caption(f"Error: {str(e)[:50]}")
            else:
                st.warning("⚠️ No images found for this prompt.")

# -----------------------------
# Footer
# -----------------------------
st.markdown("---")
st.markdown("💡 **Tip:** Use descriptive prompts for better results!")
