import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_webrtc import webrtc_streamer
import av
import speech_recognition as sr
import tempfile
import json
import re

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDENTIALS = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
client = gspread.authorize(creds)

# Replace this with the name of your Google Sheet
SHEET_NAME = "Home Inventory"
sheet = client.open(SHEET_NAME).sheet1

st.title("🏠 Home Inventory App")

# --- Add Item Form with Voice Input ---
st.header("📦 Add New Item (with optional voice input)")

spoken_text = ""
parsed_data = {"item_name": "", "container": "", "location": "", "notes": ""}

audio_data_buffer = None
use_voice = st.toggle("🎙️ Enable voice input")

if use_voice:
    st.info("Tap Start, speak clearly, then tap Stop. Once stopped, click 'Process voice input' to continue.")

    webrtc_ctx = webrtc_streamer(
        key="speech",
        audio_receiver_size=256,
        media_stream_constraints={"audio": True, "video": False},
        async_processing=False,
    )

    r = sr.Recognizer()

    if "audio_bytes" not in st.session_state:
        st.session_state.audio_bytes = None

    if webrtc_ctx.audio_receiver and not webrtc_ctx.state.playing:
        try:
            st.write("🔄 Capturing audio frames...")
            audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=5)
            audio_data_buffer = b"".join([f.to_ndarray().tobytes() for f in audio_frames])
            st.session_state.audio_bytes = audio_data_buffer
            st.success("✅ Audio captured. Now click 'Process voice input'.")
        except Exception as e:
            st.warning("⚠️ No audio captured yet or timeout.")

    if st.button("▶️ Process voice input") and st.session_state.audio_bytes:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(st.session_state.audio_bytes)
                f.flush()
                with sr.AudioFile(f.name) as source:
                    audio_data = r.record(source)
                    spoken_text = r.recognize_google(audio_data)
                    st.success(f"🎤 You said: {spoken_text}")

                    # Simple parsing logic
                    spoken_text_lower = spoken_text.lower()
                    if "note:" in spoken_text_lower:
                        parts = spoken_text_lower.split("note:")
                        spoken_text_lower = parts[0].strip()
                        parsed_data["notes"] = parts[1].strip()

                    # Look for common patterns
                    container_keywords = ["box", "suitcase", "standalone"]
                    locations = ["loft", "garage", "shed", "keller", "locker", "chest"]

                    for word in spoken_text_lower.split():
                        if any(ck in word for ck in container_keywords):
                            parsed_data["container"] = word.title()
                        if any(loc in word for loc in locations):
                            parsed_data["location"] = word.title()

                    match = re.search(r"(Box|Suitcase|Container)\s*\d+", spoken_text, re.IGNORECASE)
                    if match:
                        parsed_data["container"] = match.group(0)

                    parsed_data["item_name"] = spoken_text.split(" are ")[0].strip().title()
        except Exception as e:
            st.warning("⚠️ Voice processing failed. Try again.")

with st.form("add_item"):
    item_name = st.text_input("Item Name", value=parsed_data["item_name"] or spoken_text)
    container = st.text_input("Container / Label (Box 12, Team GB Suitcase, or (Standalone))", value=parsed_data["container"])
    location = st.text_input("Location (e.g. Old Southeast Loft, Garage, Keller)", value=parsed_data["location"])
    notes = st.text_input("Notes (optional)", value=parsed_data["notes"])
    submitted = st.form_submit_button("Add to Inventory")

    if submitted and item_name and location:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [timestamp, item_name, container, location, notes]
        sheet.append_row(new_row)
        st.success(f"Item '{item_name}' added to inventory!")

# --- Search ---
st.header("🔍 Search Inventory")
search_query = st.text_input("What are you looking for?")

if search_query:
    records = sheet.get_all_records()
    results = [row for row in records if search_query.lower() in row["Item Name"].lower()]
    if results:
        st.write(f"Found {len(results)} result(s):")
        st.table(results)
    else:
        st.warning("Item not found.")

