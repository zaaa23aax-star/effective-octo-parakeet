import streamlit as st
import requests
import pandas as pd
import time
import datetime

st.set_page_config(page_title="🧠 AI Model Tester", layout="wide")

st.title("🧠 OpenRouter AI Model Tester")
st.markdown("Test and compare text-generation models from OpenRouter dynamically!")

# --- Sidebar ---
api_key = st.sidebar.text_input("🔑 Enter your OpenRouter API Key:", type="password")
if not api_key:
    st.warning("Please enter your API key to start.")
    st.stop()

st.sidebar.markdown("[Get your API key](https://openrouter.ai/keys)")

# --- Load available models dynamically ---
@st.cache_data(ttl=3600)
def fetch_models(api_key):
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        models = [m["id"] for m in data["data"]]
        return sorted(models)
    else:
        st.error(f"❌ Could not fetch models: {res.text}")
        return []

models_list = fetch_models(api_key)
if not models_list:
    st.stop()

# --- Prompt input ---
prompt = st.text_area("📝 Enter your prompt:", height=150, placeholder="e.g. Explain quantum computing in simple terms...")

# --- Model selection with search ---
selected_models = st.multiselect(
    "🤖 Select models to test (type to search):",
    options=models_list,
    default=[models_list[0]] if models_list else [],
)

if "runs" not in st.session_state:
    st.session_state["runs"] = []

def call_model(model, prompt):
    """Send request to OpenRouter model"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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

# --- Display last runs ---
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
