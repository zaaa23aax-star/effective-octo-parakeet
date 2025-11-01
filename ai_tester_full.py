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
# API Keys Configuration
# -----------------------------
# Try to get from secrets first, fallback to manual input
try:
    OPENROUTER_API_KEY = str(st.secrets.get("OPENROUTER_API_KEY", "")).strip().strip('"').strip("'")
    SERPAPI_KEY = str(st.secrets.get("SERPAPI_KEY", "")).strip().strip('"').strip("'")
except:
    OPENROUTER_API_KEY = ""
    SERPAPI_KEY = ""

# If keys are empty, ask user to input them
if not OPENROUTER_API_KEY or not SERPAPI_KEY:
    st.warning("⚠️ API keys not found in secrets. Please enter them below:")
    
    col1, col2 = st.columns(2)
    with col1:
        OPENROUTER_API_KEY = st.text_input(
            "OpenRouter API Key:", 
            type="password",
            help="Get it from https://openrouter.ai/keys"
        )
    with col2:
        SERPAPI_KEY = st.text_input(
            "SerpAPI Key:", 
            type="password",
            help="Get it from https://serpapi.com/manage-api-key"
        )
    
    if not OPENROUTER_API_KEY or not SERPAPI_KEY:
        st.info("💡 **Tip:** Add these to Streamlit secrets to avoid entering them each time.")
        st.stop()

# Clean the keys
OPENROUTER_API_KEY = OPENROUTER_API_KEY.strip()
SERPAPI_KEY = SERPAPI_KEY.strip()

# -----------------------------
# Load Models
# -----------------------------
@st.cache_data(ttl=3600)
def fetch_models(api_key):
    """Fetch available models from OpenRouter."""
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # Filter for popular/working models
            models = [m["id"] for m in data.get("data", [])]
            return sorted(models)
        else:
            st.error(f"❌ Could not fetch models: {res.text}")
            return ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]
    except Exception as e:
        st.error(f"❌ Error fetching models: {e}")
        return ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]

# Load models
with st.spinner("Loading available models..."):
    models_list = fetch_models(OPENROUTER_API_KEY)

if not models_list:
    st.error("❌ Could not load models. Using defaults.")
    models_list = ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]

# -----------------------------
# User Input
# -----------------------------
prompt = st.text_area(
    "📝 Enter your prompt:",
    height=150,
    placeholder="e.g. A serene landscape with mountains and a lake at sunset...",
)

col1, col2 = st.columns([3, 1])
with col1:
    selected_model = st.selectbox(
        "🤖 Select AI model:", 
        models_list,
        index=0
    )
with col2:
    num_images = st.slider("🖼️ Number of images:", 1, 6, 3)

# -----------------------------
# Core Functions
# -----------------------------
def call_model(model, prompt, api_key):
    """Query OpenRouter for text output."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit-app.com",
        "X-Title": "AI Image + Text App"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        end = time.time()

        if response.status_code != 200:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except:
                pass
            return {
                "error": f"API Error (Status {response.status_code}): {error_msg}",
                "time": round(end - start, 2)
            }

        res = response.json()
        
        # Handle different response formats
        if "choices" in res and len(res["choices"]) > 0:
            text = res["choices"][0]["message"]["content"]
            tokens = res.get("usage", {}).get("total_tokens", "N/A")
            return {
                "text": text,
                "tokens": tokens,
                "time": round(end - start, 2)
            }
        else:
            return {"error": f"Unexpected response format: {res}"}
    
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Please try again."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

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
        images = data.get("images_results", [])
        return [img["original"] for img in images[:num_results] if "original" in img]
    
    except Exception as e:
        st.error(f"❌ Error searching images: {str(e)}")
        return []

# -----------------------------
# Run Button
# -----------------------------
if st.button("🚀 Generate Text + Images", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("⚠️ Please enter a prompt.")
    else:
        # Generate AI Text
        with st.spinner("🧠 Generating AI text..."):
            text_result = call_model(selected_model, prompt, OPENROUTER_API_KEY)

        if "error" in text_result:
            st.error(f"❌ {text_result['error']}")
            
            # Show helpful debugging info
            with st.expander("🔧 Debugging Information"):
                st.write("**API Key Status:**")
                st.write(f"- Key starts with: `{OPENROUTER_API_KEY[:15]}...`")
                st.write(f"- Key length: {len(OPENROUTER_API_KEY)} characters")
                st.write(f"- Model: {selected_model}")
                st.write("\n**Troubleshooting:**")
                st.write("1. Verify you have credits at https://openrouter.ai/credits")
                st.write("2. Try a different model (some require special access)")
                st.write("3. Check if your key is still valid at https://openrouter.ai/keys")
        else:
            # Show AI Response
            st.subheader("🧠 AI Response")
            st.info(f"⏱️ Generated in {text_result['time']} seconds | 🧮 Tokens used: {text_result['tokens']}")
            
            with st.container():
                st.markdown(text_result["text"])

            # Search Images
            st.divider()
            with st.spinner("🔍 Searching for related images..."):
                images = search_images(prompt, num_images, SERPAPI_KEY)

            if images:
                st.subheader("🖼️ Related Images")
                
                # Display images in rows of 3
                for i in range(0, len(images), 3):
                    cols = st.columns(3)
                    for j, url in enumerate(images[i:i+3]):
                        col = cols[j]
                        try:
                            img_response = requests.get(url, timeout=10)
                            img_response.raise_for_status()
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
                            col.error(f"⚠️ Could not load image {i+j+1}")
            else:
                st.warning("⚠️ No images found for this prompt. Try a different search term.")

# -----------------------------
# Footer
# -----------------------------
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    💡 <b>Tips:</b> Use descriptive prompts for better results | 
    Check your API credits regularly | 
    Different models may give different results
</div>
""", unsafe_allow_html=True)
