import streamlit as st
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
import json
import base64

# =========================
# AFFILIATE TAG SETTINGS
# =========================
AFFILIATE_TAG = "passionismyso-20"

def add_affiliate_tag(url):
    """Add Amazon affiliate tag properly."""
    if "amazon." not in url:
        return url
    if "tag=" in url:
        return url  # Already has tag
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}tag={AFFILIATE_TAG}"


# =========================
# CONDITIONAL GOOGLE IMPORTS
# =========================
GOOGLE_AVAILABLE = True
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception as e:
    GOOGLE_AVAILABLE = False
    GOOGLE_IMPORT_ERROR = str(e)


# =========================
# DRIVE UPLOAD FUNCTION
# =========================
def upload_to_drive(file_bytes, filename):
    """Upload file to Google Drive using service account.
    Returns: (success: bool, message: str)
    """
    if not GOOGLE_AVAILABLE:
        return False, f"Google libraries unavailable: {GOOGLE_IMPORT_ERROR}"

    try:
        service_account_info = json.loads(st.secrets["service_account"])
    except Exception:
        return False, "❌ Missing or invalid [service_account] in Streamlit secrets."

    try:
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
    except Exception as e:
        return False, f"❌ Credentials error: {e}"

    try:
        service = build("drive", "v3", credentials=creds)
        folder_id = st.secrets.get("drive_folder_id", None)

        file_metadata = {
            "name": filename,
            "mimeType": "application/pdf",
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = base64.b64encode(file_bytes).decode()

        uploaded = service.files().create(
            body=file_metadata,
            media_body=BytesIO(file_bytes),
            fields="id"
        ).execute()

        return True, f"Uploaded successfully. File ID: {uploaded.get('id')}"

    except Exception as e:
        return False, f"❌ Drive upload failed: {e}"


# =========================
# STREAMLIT UI
# =========================
st.title("Amazon Affiliate Scraper + Report Generator")
st.write("Drive Optional – Works even if Google Drive fails.")

# URL input
url = st.text_input("Enter Amazon Product URL:")

if url:
    url_with_tag = add_affiliate_tag(url)
    st.write("**Affiliate URL:**")
    st.code(url_with_tag)

    if st.button("Generate Report"):
        # SCRAPE
        try:
            r = requests.get(url)
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.find(id="productTitle").get_text(strip=True)
        except Exception:
            title = "Unknown Title"

        # CREATE REPORT
        report = f"""
        AMAZON PRODUCT REPORT
        ---------------------
        Title: {title}
        Original URL: {url}
        Affiliate URL: {url_with_tag}
        """

        report_bytes = report.encode()

        # DISPLAY REPORT
        st.subheader("Generated Report")
        st.text(report)

        # DOWNLOAD BUTTON
        st.download_button(
            "Download Report",
            data=report_bytes,
            file_name="report.txt",
            mime="text/plain"
        )

        # UPLOAD TO DRIVE
        success, msg = upload_to_drive(report_bytes, "report.txt")

        st.subheader("Google Drive Upload Status")
        if success:
            st.success(msg)
        else:
            st.error(msg)
            st.info("App continues normally — Drive is optional.")


# =========================
# DEBUG INFO IF GOOGLE FAILS
# =========================
if not GOOGLE_AVAILABLE:
    st.warning(f"Google API Unavailable: {GOOGLE_IMPORT_ERROR}")
