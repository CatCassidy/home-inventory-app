import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_webrtc import webrtc_streamer
import av
import speech_recognition as sr
import tempfile
import json

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDENTIALS = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
client = gspread.authorize(creds)

SHEET_NAME = "Home Inventory"
sheet = client.open(SHEET_NAME).sheet1

st.title("🏠 Home Inventory App")
st.caption("🔧 Voice input version: Manual Trigger v1.1")

# --- Voice Input Section ---
st.subheader("🎙️ Voice Input")

use_voice = st.toggle("Enable voice input")

spoken_text = ""
audio_ready = False
audio_file_path = None

if use_voice:
    st.info("Tap Start, speak clearly, then tap Stop. Then click 'Process Voice Input'.")

    webrtc_ctx = webrtc_streamer(
        key="voice_input",
        audio_receiver_size=256,
        media_stream_constraints={"audio": True, "video": False},
        async_processing=True,
    )

    if webrtc_ctx.audio_receiver:
        try:
            audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=3)
            audio = b"".join([f.to_ndarray().tobytes() for f in audio_frames])

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio)
                audio_file_path = f.name
                audio_ready = True
        except Exception as e:
            st.warning("⚠️ Voice recording failed. Try again.")
            audio_ready = False

    if audio_ready and audio_file_path:
        if st.button("Process Voice Input"):
            r = sr.Recognizer()
            try:
                with sr.AudioFile(audio_file_path) as source:
                    audio_data = r.record(source)
                    spoken_text = r.recognize_google(audio_data)
                    st.success(f"🎤 Transcription: {spoken_text}")
            except sr.UnknownValueError:
                st.warning("⚠️ Could not understand the audio.")
            except Exception as e:
                st.error(f"Error during transcription: {e}")

# --- Add Item Form ---
st.header("📦 Add New Item (with optional voice input)")

with st.form("add_item"):
    item_name = st.text_input("Item Name", value=spoken_text)
    container = st.text_input("Container / Label (Box 12, Team GB Suitcase, or (Standalone))")
    location = st.text_input("Location (e.g. Old Southeast Loft, Garage, Keller)")
    notes = st.text_input("Notes (optional)")
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
