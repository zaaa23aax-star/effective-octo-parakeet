import os
import time
import datetime
import requests
import streamlit as st
from io import BytesIO
from PIL import Image

# -----------------------------
# 🔑 Load API Keys (Cloud or Local)
# -----------------------------
openrouter_key = None
serpapi_key = None

try:
    # If running on Streamlit Cloud
    if "OPENROUTER_API_KEY" in st.secrets:
        openrouter_key = st.secrets["OPENROUTER_API_KEY"]
        serpapi_key = st.secrets.get("SERPAPI_KEY")
    else:
        # Local run: load from .env
        from dotenv import load_dotenv
        load_dotenv()
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        serpapi_key = os.getenv("SERPAPI_KEY")
except Exception as e:
    st.warning(f"⚠️ Could not load environment: {e}")

# -----------------------------
# 🧠 Streamlit Page Config
# -----------------------------
st.set_page_config(page_title="🧠 AI + 🖼️ Image Generator", layout="wide")

st.title("🧠 AI Text & 🖼️ Image Generator")
st.markdown("Enter a single prompt — get **AI-generated text** and **related images** instantly!")

# -----------------------------
# 🚫 Stop if API keys missing
# --
