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

# Initialize session state for API keys
if 'openrouter_key' not in st.session_state:
    st.session_state.openrouter_key = ""
if 'serpapi_key' not in st.session_state:
    st.session_state.serpapi_key = ""
if 'keys_validated' not in st.session_state:
    st.session_state.keys_validated = False

# -----------------------------
# API Key Input Section
# -----------------------------
if not st.session_state.keys_validated:
    st.markdown("### 🔑 Enter Your API Keys")
    st.info("Your keys are only stored in your browser session and are never saved.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        openrouter_input = st.text_input(
            "OpenRouter API Key:",
            type="password",
            placeholder="sk-or-v1-...",
            help="Get yours at: https://openrouter.ai/keys"
        )
    
    with col2:
        serpapi_input = st.text_input(
            "SerpAPI Key:",
            type="password",
            placeholder="Your SerpAPI key",
            help="Get yours at: https://serpapi.com/manage-api-key"
        )
    
    if st.button("✅ Validate & Continue", type="primary"):
        if not openrouter_input or not serpapi_input:
            st.error("❌ Please enter both API keys")
        else:
            # Validate OpenRouter key
            with st.spinner("Validating OpenRouter key..."):
                try:
                    test = requests.get(
                        "https://openrouter.ai/api/v1/auth/key",
                        headers={"Authorization": f"Bearer {openrouter_input}"},
                        timeout=10
                    )
                    
                    if test.status_code == 200:
                        st.session_state.openrouter_key = openrouter_input
                        st.session_state.serpapi_key = serpapi_input
                        st.session_state.keys_validated = True
                        st.success("✅ Keys validated! Reloading...")
                        st.rerun()
                    else:
                        st.error(f"❌ OpenRouter key invalid: {test.text}")
                        st.markdown("**Troubleshooting:**")
                        st.markdown("1. Make sure you have credits at https://openrouter.ai/credits")
                        st.markdown("2. Verify your key at https://openrouter.ai/keys")
                        st.markdown("3. Copy the key without any extra spaces or quotes")
                except Exception as e:
                    st.error(f"❌ Error validating key: {e}")
    
    st.stop()

# Keys are validated, show reset button in sidebar
with st.sidebar:
    st.markdown("### 🔑 API Keys")
    st.success("✅ Keys validated")
    if st.button("🔄 Reset Keys"):
        st.session_state.keys_validated = False
        st.session_state.openrouter_key = ""
        st.session_state.serpapi_key = ""
        st.rerun()

# -----------------------------
# Get API Keys from Session
# -----------------------------
OPENROUTER_API_KEY = st.session_state.openrouter_key
SERPAPI_KEY = st.session_state.serpapi_key

# -----------------------------
# Load Models
# -----------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_models(api_key):
    """Fetch available models from OpenRouter."""
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            models = [m["id"] for m in data.get("data", [])]
            # Filter for popular models
            popular = [
                "openai/gpt-4o-mini",
                "openai/gpt-3.5-turbo",
                "anthropic/claude-3-haiku",
                "anthropic/claude-3.5-sonnet",
                "google/gemini-pro",
                "meta-llama/llama-3-8b-instruct"
            ]
            # Put popular models first
            sorted_models = [m for m in popular if m in models]
            sorted_models.extend([m for m in sorted(models) if m not in popular])
            return sorted_models
        else:
            return ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]
    except:
        return ["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"]

# Load models
models_list = fetch_models(OPENROUTER_API_KEY)

# -----------------------------
# Main Interface
# -----------------------------
st.markdown("Enter a prompt to get both **AI-generated text** and **related images**!")

prompt = st.text_area(
    "📝 Your Prompt:",
    height=120,
    placeholder="e.g., A serene mountain landscape at sunset with a crystal clear lake..."
)

col1, col2 = st.columns([3, 1])
with col1:
    selected_model = st.selectbox(
        "🤖 AI Model:",
        models_list,
        index=0
    )
with col2:
    num_images = st.slider("🖼️ Images:", 1, 6, 3)

# -----------------------------
# Core Functions
# -----------------------------
def call_openrouter(model, prompt, api_key):
    """Call OpenRouter API."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "Streamlit AI App"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        elapsed = time.time() - start
        
        if response.status_code != 200:
            return {
                "error": f"Status {response.status_code}: {response.text}",
                "time": elapsed
            }
        
        data = response.json()
        return {
            "text": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", "N/A"),
            "time": round(elapsed, 2)
        }
    
    except Exception as e:
        return {"error": str(e)}

def search_images(query, num, api_key):
    """Search images with SerpAPI."""
    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "tbm": "isch",
                "num": num,
                "api_key": api_key
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return [
                img["original"] 
                for img in data.get("images_results", [])[:num]
                if "original" in img
            ]
        return []
    except:
        return []

# -----------------------------
# Generate Button
# -----------------------------
if st.button("🚀 Generate", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("⚠️ Please enter a prompt")
    else:
        # Generate text
        with st.spinner("🧠 Generating AI response..."):
            result = call_openrouter(selected_model, prompt, OPENROUTER_API_KEY)
        
        if "error" in result:
            st.error(f"❌ Error: {result['error']}")
            
            with st.expander("🔍 Debug Info"):
                st.code(f"Model: {selected_model}\nKey: {OPENROUTER_API_KEY[:20]}...")
                st.markdown("**Try:**")
                st.markdown("- Use a different model")
                st.markdown("- Check credits at https://openrouter.ai/credits")
                st.markdown("- Reset your keys and try again")
        else:
            # Display AI response
            st.success(f"✅ Generated in {result['time']}s | Tokens: {result['tokens']}")
            
            with st.container():
                st.markdown("### 🧠 AI Response")
                st.markdown(result["text"])
            
            st.divider()
            
            # Search images
            with st.spinner("🔍 Finding images..."):
                images = search_images(prompt, num_images, SERPAPI_KEY)
            
            if images:
                st.markdown("### 🖼️ Related Images")
                
                # Display in grid
                for i in range(0, len(images), 3):
                    cols = st.columns(3)
                    for j, img_url in enumerate(images[i:i+3]):
                        with cols[j]:
                            try:
                                img_data = requests.get(img_url, timeout=10).content
                                img = Image.open(BytesIO(img_data))
                                st.image(img, use_container_width=True)
                                st.download_button(
                                    "⬇️",
                                    data=img_data,
                                    file_name=f"image_{i+j+1}.jpg",
                                    mime="image/jpeg",
                                    key=f"dl_{i+j}",
                                    use_container_width=True
                                )
                            except:
                                st.error(f"❌ Failed to load image {i+j+1}")
            else:
                st.warning("⚠️ No images found")

# Footer
st.divider()
st.caption("💡 Tip: Use descriptive prompts for better results!")
