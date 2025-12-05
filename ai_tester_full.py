import streamlit as st
import requests
import re
import datetime
from io import BytesIO
from PIL import Image

# -----------------------------
# Config / Page
# -----------------------------
st.set_page_config(page_title="🛍️ Amazon Finder (Advanced Models)", layout="wide")
st.title("🛍️ Amazon Product Finder — Advanced Model Selector (Option B)")

# -----------------------------
# Secrets / Keys
# -----------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
except Exception as e:
    st.error("❌ Add OpenRouter, Groq, and SerpAPI keys in Streamlit secrets.")
    st.stop()

# -----------------------------
# Affiliate helper
# -----------------------------
AFFILIATE_TAG = "passionismyso-20"
def add_affiliate_tag(url: str) -> str:
    if not url:
        return url
    if "tag=" in url:
        return url
    connector = "&" if "?" in url else "?"
    return f"{url}{connector}tag={AFFILIATE_TAG}"

# -----------------------------
# Model catalog (categories + descriptions)
# -----------------------------
MODEL_CATALOG = {
    "Free": {
        "mistralai/mixtral-8x7b-instruct:free": "Mixtral free instruct — compact & creative.",
        "mistralai/mistral-7b-instruct:free": "Mistral 7B free — good balance of quality and cost.",
        "qwen/qwen2-7b-instruct:free": "Qwen 7B free — lightweight instruct model.",
        "huggingfaceh4/zephyr-7b-beta:free": "Zephyr 7B beta — experimental conversational model."
    },
    "Fast": {
        "mixtral-8x7b": "Mixtral 8x7B — fast & efficient for short outputs.",
        "llama-3.1-8b-instant": "Llama 3.1 8B Instant — low latency for quick responses.",
        "google/gemma-2-9b-it": "Gemma 2 9B — optimized for instruction tasks."
    },
    "Premium": {
        "openai/gpt-4.1-mini": "GPT-4.1 Mini — high-quality summaries & marketing text.",
        "openai/gpt-4.1": "GPT-4.1 — best-in-class for creative descriptions.",
        "qwen/qwen2-72b-instruct": "Qwen2 72B — very large model for quality-first generation.",
        "meta-llama/llama-3.1-70b": "Llama 3.1 70B — premium performance for complex prompts."
    }
}

# Flatten models for easier fallback ordering and mapping display name -> id
def flatten_catalog(catalog):
    flat = {}
    for cat, models in catalog.items():
        for mid, desc in models.items():
            flat[mid] = {"category": cat, "description": desc}
    return flat

FLAT_MODELS = flatten_catalog(MODEL_CATALOG)
ALL_MODEL_IDS = list(FLAT_MODELS.keys())

# -----------------------------
# UI: Left sidebar - Model selection controls
# -----------------------------
st.sidebar.header("Model Controls — Advanced Mode (B)")
model_search = st.sidebar.text_input("Search models", placeholder="filter by name or provider (e.g., 'gpt', 'llama', 'mistral')")

# Tabs for categories
selected_models = []  # will collect models checked by user
with st.sidebar:
    tab_free, tab_fast, tab_premium = st.tabs(["Free", "Fast", "Premium"])
    def list_models_in_tab(tab, cat_name):
        checked = []
        for mid, desc in MODEL_CATALOG[cat_name].items():
            if model_search and model_search.lower() not in (mid + desc).lower():
                continue
            label = f"{mid} — {desc}"
            if st.checkbox(label, key=f"{cat_name}-{mid}"):
                checked.append(mid)
        return checked

    with tab_free:
        free_checked = list_models_in_tab(tab_free, "Free")
    with tab_fast:
        fast_checked = list_models_in_tab(tab_fast, "Fast")
    with tab_premium:
        premium_checked = list_models_in_tab(tab_premium, "Premium")

    # Combine checked
    selected_models = free_checked + fast_checked + premium_checked

    st.markdown("---")
    st.write(f"Selected models: **{len(selected_models)}**")
    auto_fallback = st.checkbox("Enable Auto-Fallback across ALL models (recommended)", value=True)
    manual_primary = st.selectbox("Pick Primary Model (manual):", options=["(use auto selection)"] + selected_models, index=0 if "(use auto selection)" in ["(use auto selection)"] else 0)
    # Allow user to reorder backups (simple: multiselect for backups)
    backup_models = st.multiselect("Pick Backup Models (ordered):", options=[m for m in selected_models if m != manual_primary], default=[])

# If user didn't select any models, prefill with some sensible defaults
if not selected_models:
    # use a small default set (from earlier list)
    selected_models = [
        "mistralai/mixtral-8x7b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "mixtral-8x7b",
        "openai/gpt-4.1-mini",
        "openai/gpt-4.1"
    ]

# Build effective fallback list
def build_fallback_order(primary_choice, chosen_backups, auto_all=True):
    tried = []
    if primary_choice and primary_choice != "(use auto selection)":
        tried.append(primary_choice)
    # then user backups in order
    for b in chosen_backups:
        if b not in tried:
            tried.append(b)
    # then auto fallback across everything else if enabled
    if auto_all:
        for m in ALL_MODEL_IDS:
            if m not in tried:
                tried.append(m)
    return tried

effective_order = build_fallback_order(manual_primary if manual_primary != "(use auto selection)" else None, backup_models, auto_all=auto_fallback)

# Display model tooltip table in main area
st.markdown("### Model Catalog (hover descriptions in the list)")
for cat in MODEL_CATALOG:
    with st.expander(f"{cat} models ({len(MODEL_CATALOG[cat])})", expanded=False):
        for mid, desc in MODEL_CATALOG[cat].items():
            if model_search and model_search.lower() not in (mid + desc).lower():
                continue
            st.write(f"- `{mid}` — {desc}")

# -----------------------------
# Amazon search input
# -----------------------------
st.markdown("---")
product_name = st.text_input("🔍 Product Name", placeholder="e.g., wireless headphones")

# -----------------------------
# Amazon search functions (SerpAPI + Scraper fallback)
# -----------------------------
def search_serpapi(query):
    if not SERPAPI_KEY:
        return []
    url = "https://serpapi.com/search.json"
    params = {"engine": "amazon", "k": query, "amazon_domain": "amazon.com", "api_key": SERPAPI_KEY}
    try:
        res = requests.get(url, params=params, timeout=15).json()
        for item in res.get("organic_results", []):
            if item.get("link") and "amazon.com" in item["link"] and item.get("price"):
                return [{
                    "title": item.get("title"),
                    "asin": item.get("asin"),
                    "link": add_affiliate_tag(item.get("link")),
                    "image": item.get("thumbnail"),
                    "price": item.get("price")
                }]
        return []
    except Exception:
        return []

def scrape_amazon(query):
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        page = requests.get(url, headers=headers, timeout=10).text
        asin_match = re.search(r'data-asin="(\w+)"', page)
        title_match = re.search(r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', page)
        img_match = re.search(r'<img.*?class="s-image".*?src="(.*?)"', page)
        price_match = re.search(r'\$\d[\d,]*\.?\d*', page)
        if asin_match and title_match and price_match:
            asin = asin_match.group(1)
            product_link = add_affiliate_tag(f"https://www.amazon.com/dp/{asin}")
            return [{
                "asin": asin,
                "title": title_match.group(1),
                "image": img_match.group(1) if img_match else None,
                "link": product_link,
                "price": price_match.group(0)
            }]
        return []
    except Exception:
        return []

def search_amazon_fallback(query):
    results = search_serpapi(query)
    if results:
        return results, "SerpAPI 🔥"
    results = scrape_amazon(query)
    if results:
        return results, "Scraper fallback 🖇️"
    return [], "No deliverable product found"

# -----------------------------
# Model call helper (decides endpoint)
# -----------------------------
def call_model_generate(model_id: str, prompt: str, timeout=20):
    """
    Try to call the given model. Heuristics:
    - If model_id contains 'llama-3' or 'llama3' or 'groq' -> call GROQ endpoint
    - Otherwise -> call OpenRouter endpoint
    Returns text or raises Exception
    """
    # Prepare payload for chat-based API (both endpoints use chat completions style)
    if any(flag in model_id.lower() for flag in ["llama-3", "llama3", "groq", "llama-3.1", "llama-3.1-70b", "llama-3.1-8b"]):
        # use Groq
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        data = {"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 256}
    else:
        # use OpenRouter
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data = {"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 256}
    r = requests.post(url, json=data, headers=headers, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    # flexible extraction for different providers
    if isinstance(j.get("choices"), list) and j["choices"]:
        msg = j["choices"][0].get("message") or j["choices"][0].get("text")
        if isinstance(msg, dict):
            return msg.get("content", "").strip()
        elif isinstance(msg, str):
            return msg.strip()
    # Some endpoints return top-level 'text'
    if isinstance(j.get("text"), str):
        return j["text"].strip()
    # Fallback
    raise Exception("No textual response from model")

# -----------------------------
# Pinterest description generator (tries primary, then backups, then auto-fallback)
# -----------------------------
def generate_pinterest_description_with_fallback(product, model_order):
    prompt = f"""
Create a Pinterest-style marketing description for this Amazon product:

Title: {product['title']}
ASIN: {product['asin']}

Write 2-3 short, engaging sentences:
- Use emotional, lifestyle language
- Highlight benefits, not just features
- Include relevant emojis naturally
- Make readers want to click and buy
- Keep it under 80 words
"""
    last_exception = None
    for mid in model_order:
        try:
            txt = call_model_generate(mid, prompt)
            if txt and len(txt.strip()) > 10:
                return txt, mid
        except Exception as e:
            last_exception = e
            # try next model
            continue
    # If everything fails, return fallback text and None model
    fallback_text = f"✨ {product['title']} is a must-have! ASIN: {product['asin']} 🌟"
    return fallback_text, None

# -----------------------------
# Report generator when fallback used
# -----------------------------
def generate_fallback_report(product, source, used_model=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""Amazon Deliverable Product Report (Fallback)
--------------------------------------------
Retrieved At: {timestamp}

Source Used: {source}
Model Used (for description): {used_model or 'N/A'}

Product Title:
{product['title']}

ASIN:
{product['asin']}

Price:
{product['price']}

Affiliate Link:
{product['link']}

--------------------------------------------
"""
    return report

# -----------------------------
# Display product function
# -----------------------------
def display_product(product, source_name, description, desc_model_id):
    st.info(f"Results from: {source_name}")
    st.subheader(product["title"])
    col1, col2 = st.columns([1, 2])
    with col1:
        if product.get("image"):
            try:
                st.image(product["image"])
            except Exception:
                pass
        st.markdown(f"**ASIN:** `{product['asin']}`")
        st.markdown(f"**Price:** {product['price']}")
        st.markdown("")  # spacing
        st.markdown(f"[Open on Amazon]({add_affiliate_tag(product['link'])})")
    with col2:
        st.markdown(f"**Pinterest-Style Description:**")
        st.write(description)
        if desc_model_id:
            st.caption(f"Generated by model: `{desc_model_id}`")

# -----------------------------
# Main search button action
# -----------------------------
st.markdown("---")
if st.button("🔍 Search Deliverable Product"):
    if not product_name.strip():
        st.warning("Type a product name first.")
    else:
        products, source_name = search_amazon_fallback(product_name)
        if not products:
            st.error("No deliverable products found.")
        else:
            product = products[0]
            # Prepare model order:
            # If user manually set a primary, use it first; otherwise use effective_order
            model_order = effective_order.copy()
            if manual_primary and manual_primary != "(use auto selection)":
                # ensure manual primary first
                if manual_primary in model_order:
                    model_order.remove(manual_primary)
                model_order.insert(0, manual_primary)

            # Generate description with fallback
            with st.spinner("Generating Pinterest-style description (may try multiple models)..."):
                description, used_model = generate_pinterest_description_with_fallback(product, model_order)

            # Display
            display_product(product, source_name, description, used_model)

            # If fallback (scraper) used — provide downloadable report
            if source_name != "SerpAPI 🔥":
                st.success("Fallback was used (Scraper). Download report below.")
                report_text = generate_fallback_report(product, source_name, used_model)
                st.download_button(
                    label="📥 Download Fallback Report (.txt)",
                    data=report_text,
                    file_name=f"amazon_fallback_report_{product['asin']}.txt",
                    mime="text/plain"
                )

            # Also offer to regenerate description with a specific chosen model (manual override)
            st.markdown("---")
            st.markdown("#### Regenerate description with a specific model (manual override)")
            chosen_override = st.selectbox("Choose model to force (optional):", options=["(none)"] + ALL_MODEL_IDS)
            if st.button("Regenerate with chosen model"):
                if chosen_override == "(none)":
                    st.warning("Pick a model first.")
                else:
                    try:
                        with st.spinner(f"Calling {chosen_override}..."):
                            text_override = call_model_generate(chosen_override, f"Create a Pinterest-style description for: {product['title']}\nASIN: {product['asin']}\nShort, emotional, 2-3 sentences, include emojis, <80 words.")
                        st.success("Regenerated description:")
                        st.write(text_override)
                        st.caption(f"Generated by `{chosen_override}`")
                    except Exception as e:
                        st.error(f"Model call failed: {str(e)}")
