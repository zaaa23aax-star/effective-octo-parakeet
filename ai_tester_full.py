import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import datetime
import time
from fpdf import FPDF

st.set_page_config(page_title="🧠 AI Model Tester", layout="wide")

# --- Sidebar setup ---
st.sidebar.title("🧠 AI Model Tester")
st.sidebar.markdown("Test and compare text generation models via OpenRouter API.")

# Ask for API key each session
api_key = st.sidebar.text_input("🔑 Enter your OpenRouter API Key:", type="password")
if not api_key:
    st.warning("Please enter your API key to start.")
    st.stop()

# Prompt input
prompt = st.text_area("📝 Enter your test prompt:", height=150)

# Select models
models = st.multiselect(
    "Select AI Models to Compare:",
    ["gpt-4o-mini", "gpt-4o", "meta-llama/llama-3.1-70b-instruct", "mistralai/mixtral-8x7b"],
    default=["gpt-4o-mini"],
)

if "runs" not in st.session_state:
    st.session_state["runs"] = []

# Function to call model
def call_model(model, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    start = time.time()
    r = requests.post(url, headers=headers, json=payload)
    end = time.time()
    if r.status_code != 200:
        return {"error": r.text}
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", "N/A")
    return {"text": content, "tokens": tokens, "time": round(end - start, 2)}

# Run button
if st.button("🚀 Run Test"):
    if not prompt.strip():
        st.warning("Please enter a prompt first.")
    else:
        results = []
        for model in models:
            with st.spinner(f"Testing {model}..."):
                res = call_model(model, prompt)
                results.append({"model": model, **res})

        st.session_state["runs"].append({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "prompt": prompt,
            "results": results,
        })
        st.success("✅ Test completed!")

# --- Display results ---
for run in reversed(st.session_state["runs"][-3:]):
    st.markdown(f"## 🧾 Test Run — {run['timestamp']}")
    st.write(f"**Prompt:** {run['prompt']}")

    df = pd.DataFrame(run["results"])
    st.dataframe(df)

    if "tokens" in df and df["tokens"].iloc[0] != "N/A":
        fig = px.bar(df, x="model", y="tokens", title="Token Usage per Model")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No token data available for this run.")
