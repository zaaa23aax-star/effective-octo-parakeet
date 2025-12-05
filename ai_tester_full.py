# app.py
import streamlit as st
import requests
import json
import re
from io import BytesIO
from PIL import Image
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime

# =========================
# Config / Page
# =========================
st.set_page_config(page_title="🛍️ Amazon Finder + Drive (Optional)", layout="wide")
st.title("🛍️ Amazon Product Finder — Pinterest Style (Drive optional)")

# =========================
# Constants / Curated Models
# =========================
AFFILIATE_TAG = "passionismyso-20"
DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", None)

# Curated model list (B)
MODEL_CATALOG = {
    "Mixtral 8x7B (free)": "mistralai/mixtral-8x7b-instruct:free",
    "Mistral 7B (free)": "mistralai/mistral-7b-instruct:free",
    "Llama 3 8B (Groq)": "llama3-8b-8192",
    "GPT-4.1 Mini": "openai/gpt-4.1-mini",
    "Gemma 2 9B": "google/gemma-2-9b-it",
    "Qwen2 7B": "qwen/qwen2-7b-instruct:free",
    "Zephyr 7B (free)": "huggingfaceh4/zephyr-7b-beta:free",
    "Mixtral 8x7B (fast)": "mixtral-8x7b",
    "Gemma 2 27B": "google/gemma-2-27b-it",
    "Llama 3 70B (premium)": "meta-llama/llama-3.1-70b"
}

model_choice = st.selectbox("🤖 Primary model", list(MODEL_CATALOG.keys()))
backup_models = st.multiselect("🛡️ Backup models (ordered)", [m for m in MODEL_CATALOG.keys() if m != model_choice])

# =========================
# Robust Amazon affiliate tag function
# =========================
def add_amazon_affiliate_tag(url: str) -> str:
    try:
        if not url:
            return url
        parsed = urlparse(url)
        if "amazon." not in parsed.netloc.lower() and "amazon." not in parsed.path.lower():
            return url  # not amazon
        q = parse_qs(parsed.query)
        # Replace tag regardless of existing
        q["tag"] = [AFFILIATE_TAG]
        new_query = urlencode(q, doseq=True)
        updated = urlunparse(parsed._replace(query=new_query))
        return updated
    except Exception:
        # Fallback simple append
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}tag={AFFILIATE_TAG}"

# =========================
# Optional Google Drive (service account)
# =========================
GOOGLE_AVAILABLE = True
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
except Exception as e:
    GOOGLE_AVAILABLE = False
    GOOGLE_IMPORT_ERROR = str(e)

def get_drive_service():
    if not GOOGLE_AVAILABLE:
        return None, "google libs not installed: " + GOOGLE_IMPORT_ERROR
    if "SERVICE_ACCOUNT_JSON" not in st.secrets:
        return None, "SERVICE_ACCOUNT_JSON missing in st.secrets"
    try:
        sa_info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
    except Exception as e:
        return None, f"service account JSON invalid: {e}"
    try:
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/drive"])
        svc = build("drive", "v3", credentials=creds)
        return svc, None
    except Exception as e:
        return None, f"failed to build drive service: {e}"

drive_service, drive_err = get_drive_service()

# Drive helper: find file by name in folder
def find_file_in_folder(filename, folder_id):
    try:
        q = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        res = drive_service.files().list(q=q, fields="files(id,name)").execute()
        files = res.get("files", [])
        return files[0] if files else None
    except Exception as e:
        raise RuntimeError(f"Drive find error: {e}")

# Drive upload/update
def upload_or_update_text(filename, text, folder_id):
    if not drive_service:
        return False, "Drive not configured: " + (drive_err or "no service")
    try:
        existing = find_file_in_folder(filename, folder_id)
    except Exception as e:
        return False, f"Drive query failed: {e}"
    try:
        bio = BytesIO(text.encode("utf-8"))
        media = MediaIoBaseUpload(bio, mimetype="text/plain")
        if existing:
            drive_service.files().update(fileId=existing["id"], media_body=media).execute()
            return True, ("updated", existing["id"])
        else:
            meta = {"name": filename, "parents": [folder_id]} if folder_id else {"name": filename}
            f = drive_service.files().create(body=meta, media_body=media, fields="id").execute()
            return True, ("created", f.get("id"))
    except Exception as e:
        return False, f"Drive upload error: {e}"

# Append to master JSON log (create or update)
def append_session_to_master_log(entry, filename="amazon_sessions_log.json", folder_id=None):
    if not drive_service:
        return False, "Drive not configured"
    try:
        existing = find_file_in_folder(filename, folder_id)
    except Exception as e:
        return False, f"Drive query failed: {e}"
    try:
        if existing:
            # download existing
            request = drive_service.files().get_media(fileId=existing["id"])
            fh = BytesIO()
            downloader = MediaIoBaseUpload  # not used, we use get_media + io
            # Using simple download via media -> workaround:
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            content = fh.read().decode("utf-8")
            try:
                data = json.loads(content)
            except:
                data = []
            if not isinstance(data, list):
                data = [data]
            data.append(entry)
            new_text = json.dumps(data, ensure_ascii=False, indent=2)
            # update
            bio = BytesIO(new_text.encode("utf-8"))
            media = MediaIoBaseUpload(bio, mimetype="application/json")
            drive_service.files().update(fileId=existing["id"], media_body=media).execute()
            return True, ("updated", existing["id"])
        else:
            # create new with list
            data = [entry]
            new_text = json.dumps(data, ensure_ascii=False, indent=2)
            bio = BytesIO(new_text.encode("utf-8"))
            media = MediaIoBaseUpload(bio, mimetype="application/json")
            meta = {"name": filename}
            if folder_id:
                meta["parents"] = [folder_id]
            f = drive_service.files().create(body=meta, media_body=media, fields="id").execute()
            return True, ("created", f.get("id"))
    except Exception as e:
        return False, f"Drive log append error: {e}"

# =========================
# SerpAPI + Scraper search
# =========================
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")

def search_serpapi(query):
    if not SERPAPI_KEY:
        return []
    try:
        url = "https://serpapi.com/search.json"
        params = {"engine":"amazon","k":query,"amazon_domain":"amazon.com","api_key":SERPAPI_KEY}
        r = requests.get(url, params=params, timeout=15).json()
        for it in r.get("organic_results", []):
            link = it.get("link")
            price = it.get("price")
            if link and price and "amazon" in link:
                return [{
                    "title": it.get("title"),
                    "asin": it.get("asin"),
                    "link": add_amazon_affiliate_tag(link),
                    "image": it.get("thumbnail"),
                    "price": it.get("price")
                }]
        return []
    except Exception:
        return []

def scrape_amazon(query):
    try:
        url = f"https://www.amazon.com/s?k={query.replace(' ','+')}"
        headers = {"User-Agent":"Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).text
        asin_m = re.search(r'data-asin="(\w+)"', r)
        title_m = re.search(r'<span class="a-size-medium a-color-base a-text-normal">(.+?)</span>', r)
        img_m = re.search(r'<img.*?class="s-image".*?src="(.*?)"', r)
        price_m = re.search(r'\$\d[\d,]*\.?\d*', r)
        if asin_m and title_m and price_m:
            asin = asin_m.group(1)
            title = title_m.group(1)
            image = img_m.group(1) if img_m else None
            price = price_m.group(0)
            link = add_amazon_affiliate_tag(f"https://www.amazon.com/dp/{asin}")
            return [{
                "title": title,
                "asin": asin,
                "link": link,
                "image": image,
                "price": price
            }]
    except Exception:
        pass
    return []

def search_amazon_fallback(query):
    r = search_serpapi(query)
    if r:
        return r, "SerpAPI"
    r2 = scrape_amazon(query)
    if r2:
        return r2, "Scraper"
    return [], "No Results"

# =========================
# Model call helpers
# =========================
OPENROUTER_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
GROQ_KEY = st.secrets.get("GROQ_API_KEY", "")

def call_model_once(model_id, prompt, timeout=20):
    # heuristic for Groq/llama -> GROQ, else OpenRouter
    try:
        if any(k in model_id.lower() for k in ["llama-3","llama3","groq"]):
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_KEY}"}
            data = {"model": model_id, "messages": [{"role":"user","content":prompt}]}
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type":"application/json"}
            data = {"model": model_id, "messages": [{"role":"user","content":prompt}]}
        r = requests.post(url, json=data, headers=headers, timeout=timeout)
        j = r.json()
        # flexible extraction
        if isinstance(j.get("choices"), list) and j["choices"]:
            msg = j["choices"][0].get("message") or j["choices"][0].get("text")
            if isinstance(msg, dict):
                return msg.get("content","").strip()
            elif isinstance(msg, str):
                return msg.strip()
        if isinstance(j.get("text"), str):
            return j.get("text").strip()
        return ""
    except Exception:
        return ""

def generate_pinterest_description(product, primary_model, backup_list):
    prompt = f"""Create a Pinterest-style marketing description for this product (2-3 short sentences, <80 words, include emojis naturally).
Title: {product['title']}
ASIN: {product.get('asin','N/A')}"""
    tried_models = [MODEL_CATALOG[primary_model]] + [MODEL_CATALOG[b] for b in backup_list if b in MODEL_CATALOG]
    # then add rest of catalog as ultimate fallback
    for mid in MODEL_CATALOG.values():
        if mid not in tried_models:
            tried_models.append(mid)
    for mid in tried_models:
        txt = call_model_once(mid, prompt)
        if txt and len(txt) > 10 and "must-have" not in txt.lower():
            return txt, mid
    # final fallback
    return f"✨ {product['title']} is a must-have! ASIN: {product.get('asin','N/A')} 🌟", None

# =========================
# UI & Main flow
# =========================
st.markdown("---")
st.write("Search a product (SerpAPI first, scraper fallback).")

product_query = st.text_input("Product name", placeholder="e.g. wireless headphones")
if st.button("🔍 Search Deliverable Product"):
    if not product_query.strip():
        st.warning("Type a product name first.")
    else:
        with st.spinner("Searching Amazon..."):
            products, source = search_amazon_fallback(product_query)
        if not products:
            st.error("No deliverable products found.")
        else:
            product = products[0]
            st.success(f"Found: {product['title']}")
            cols = st.columns([1,2])
            with cols[0]:
                if product.get("image"):
                    try:
                        st.image(product["image"], width=240)
                    except Exception:
                        pass
                st.markdown(f"**ASIN:** `{product.get('asin','N/A')}`")
                st.markdown(f"**Price:** {product.get('price','N/A')}")
                st.markdown(f"[Open on Amazon]({product['link']})")
            with cols[1]:
                desc, used_model = generate_pinterest_description(product, model_choice, backup_models)
                st.markdown("### Pinterest-style description")
                st.write(desc)
                if used_model:
                    st.caption(f"Generated with model id: {used_model}")
                # manual regeneration
                st.markdown("---")
                st.markdown("Regenerate manually with a chosen model:")
                manual = st.selectbox("Force model (optional)", ["(none)"] + list(MODEL_CATALOG.keys()))
                if st.button("Regenerate with chosen model"):
                    if manual == "(none)":
                        st.warning("Choose a model first.")
                    else:
                        forced = call_model_once(MODEL_CATALOG[manual], f"Create a Pinterest style description for: {product['title']}\nASIN: {product.get('asin','N/A')}\n2-3 short sentences, <80 words, include emojis.")
                        if forced:
                            st.success("Regenerated:")
                            st.write(forced)
                        else:
                            st.error("Model call failed.")

            # Build report
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            report = {
                "timestamp": timestamp,
                "query": product_query,
                "source": source,
                "product": {
                    "title": product.get("title"),
                    "asin": product.get("asin"),
                    "price": product.get("price"),
                    "image": product.get("image"),
                    "affiliate_link": product.get("link")
                },
                "description": {"text": desc, "model_used": used_model}
            }
            report_text = json.dumps(report, ensure_ascii=False, indent=2)

            # Download button always available
            st.download_button("📥 Download report (.json)", data=report_text, file_name=f"{(product.get('asin') or 'product')}_report.json", mime="application/json")

            # Try upload to Drive if available
            if drive_service:
                st.info("Attempting to save report to Google Drive...")
                ok, res = append_session_to_master_log(report, filename="amazon_sessions_log.json", folder_id=DRIVE_FOLDER_ID)
                if ok:
                    st.success(f"Saved session log: {res}")
                else:
                    st.warning(f"Could not append to master log: {res}")
                    # fallback: try to upload single report file
                    ok2, res2 = upload_or_update_text(f"{(product.get('asin') or 'product')}_report.txt", report_text, DRIVE_FOLDER_ID)
                    if ok2:
                        st.success(f"Uploaded single report: {res2}")
                    else:
                        st.error(f"Drive save failed: {res2}")
            else:
                st.info("Google Drive not configured or unavailable — report ready to download locally.")
