import streamlit as st
import requests
import time
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
    
    # Clean the keys (remove any extra whitespace, quotes, etc.)
    OPENROUTER_API_KEY = str(OPENROUTER_API_KEY).strip().strip('"').strip("'")
    SERPAPI_KEY = str(SERPAPI_KEY).strip().strip('"').strip("'")
    
except Exception as e:
    st.error("❌ Missing API keys in Streamlit Secrets. Please add them in your app settings.")
    st.info("""
    **How to add secrets:**
    1. Go to your Streamlit app settings
    2. Click 'Secrets'
    3. Add:
    ```
    OPENROUTER_API_KEY = "sk-or-v1-your-key-here"
    SERPAPI_KEY = "your-serpapi-key-here"
    ```
    """)
    st.stop()

# -----------------------------
# Load Models
# -----------------------------
@st.cache_data(ttl=3600)
def fetch_models(api_key):
    """Fetch available models from OpenRouter."""
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            all_models = [m["id"] for m in data["data"]]
            
            # Prioritize reliable models at the top
            priority_models = [
                "openai/gpt-3.5-turbo",
                "openai/gpt-4o-mini",
                "anthropic/claude-3-haiku",
                "google/gemini-flash-1.5",
                "meta-llama/llama-3-8b-instruct"
            ]
            
            # Put priority models first, then the rest
            sorted_models = [m for m in priority_models if m in all_models]
            sorted_models.extend([m for m in sorted(all_models) if m not in priority_models])
            
            return sorted_models
        else:
            st.error(f"❌ Could not fetch models: {res.text}")
            return ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]
    except Exception as e:
        st.error(f"❌ Error fetching models: {e}")
        return ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]

models_list = fetch_models(OPENROUTER_API_KEY)

if not models_list:
    st.error("❌ No models available. Please check your API key.")
    st.stop()

# -----------------------------
# User Input
# -----------------------------
prompt = st.text_area(
    "📝 Enter your prompt:",
    height=150,
    placeholder="e.g. A serene landscape with AI explaining the beauty of nature...",
)

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    selected_model = st.selectbox(
        "🤖 Primary Model:",
        models_list,
        index=0,
        help="First model to try"
    )
with col2:
    backup_model = st.selectbox(
        "🔄 Backup Model:",
        ["None"] + models_list,
        index=0,
        help="Fallback if primary fails"
    )
with col3:
    num_images = st.slider("🖼️ Images:", 1, 6, 3)

# -----------------------------
# Core Functions
# -----------------------------
def call_model(model, prompt, api_key):
    """Query OpenRouter for text output."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
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
    
    except Exception as e:
        return {"error": str(e)}

def search_images(query, num_results, api_key):
    """Search Google Images using SerpAPI."""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "tbm": "isch",
        "num": num_results,
        "api_key": api_key
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            st.error(f"❌ Image search failed: {res.text}")
            return []
        
        data = res.json()
        return [img["original"] for img in data.get("images_results", [])[:num_results] if "original" in img]
    except Exception as e:
        st.error(f"❌ Error searching images: {e}")
        return []

# -----------------------------
# Run Button
# -----------------------------
if st.button("🚀 Generate Text + Images", type="primary"):
    if not prompt.strip():
        st.warning("⚠️ Please enter a prompt.")
    else:
        # Try primary model
        with st.spinner(f"🧠 Generating with {selected_model}..."):
            text_result = call_model(selected_model, prompt, OPENROUTER_API_KEY)

        # If primary fails and backup is selected, try backup
        if "error" in text_result and backup_model != "None":
            st.warning(f"⚠️ Primary model failed: {text_result['error']}")
            st.info(f"🔄 Trying backup model: {backup_model}...")
            
            with st.spinner(f"🧠 Generating with {backup_model}..."):
                text_result = call_model(backup_model, prompt, OPENROUTER_API_KEY)

        # Check final result
        if "error" in text_result:
            st.error(f"❌ Generation failed: {text_result['error']}")
            
            with st.expander("🔍 Troubleshooting"):
                st.markdown(f"**Primary Model:** {selected_model}")
                st.markdown(f"**Backup Model:** {backup_model}")
                st.markdown(f"**API Key (first 20 chars):** `{OPENROUTER_API_KEY[:20]}...`")
                st.markdown("")
                st.markdown("**Common fixes:**")
                st.markdown("1. ✅ Check you have credits: https://openrouter.ai/credits")
                st.markdown("2. ✅ Try `openai/gpt-3.5-turbo` as primary (most reliable)")
                st.markdown("3. ✅ Verify key is valid: https://openrouter.ai/keys")
                st.markdown("4. ✅ Some models need approval - try a different one")
        else:
            # Display AI response
            st.subheader("🧠 AI Response")
            st.info(f"⏱️ {text_result['time']} sec | 🧮 Tokens: {text_result['tokens']}")
            st.write(text_result["text"])

            # Search images
            st.divider()
            with st.spinner("🔍 Searching related images..."):
                images = search_images(prompt, num_images, SERPAPI_KEY)

            if images:
                st.subheader("🖼️ Related Images")
                
                # Display in rows of 3
                for i in range(0, len(images), 3):
                    cols = st.columns(3)
                    for j, url in enumerate(images[i:i+3]):
                        col = cols[j]
                        try:
                            img_response = requests.get(url, timeout=10)
                            img_data = img_response.content
                            img = Image.open(BytesIO(img_data))
                            
                            col.image(img, use_container_width=True)
                            col.download_button(
                                label="⬇️ Download",
                                data=img_data,
                                file_name=f"image_{i+j+1}.jpg",
                                mime="image/jpeg",
                                key=f"download_{i+j}",
                                use_container_width=True
                            )
                        except Exception as e:
                            col.error(f"⚠️ Could not load image")
            else:
                st.warning("⚠️ No images found for this prompt.")

# -----------------------------
# Footer
# -----------------------------
st.divider()
st.markdown("💡 **Tip:** Set backup to `openai/gpt-3.5-turbo` for most reliable results!")
