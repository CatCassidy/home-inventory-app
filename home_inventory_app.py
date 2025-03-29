import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, WebRtcMode  # ✅ Fixed import
import av
import speech_recognition as sr
import tempfile
import json
import time

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDENTIALS = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
client = gspread.authorize(creds)

SHEET_NAME = "Home Inventory"
sheet = client.open(SHEET_NAME).sheet1

st.title("🏠 Home Inventory App")
st.caption("🔧 Voice input version: Manual Trigger v1.2")

# Initialize session state
if 'spoken_text' not in st.session_state:
    st.session_state.spoken_text = ""
if 'audio_ready' not in st.session_state:
    st.session_state.audio_ready = False
if 'audio_file_path' not in st.session_state:
    st.session_state.audio_file_path = None

# --- Voice Input Section ---
st.subheader("🎙️ Voice Input")

use_voice = st.toggle("Enable voice input")

if use_voice:
    st.info("1. Tap START and speak clearly\n2. Tap STOP when finished\n3. Click PROCESS VOICE INPUT")

    def audio_frame_callback(frame):
        if not hasattr(audio_frame_callback, "audio_buffer"):
            audio_frame_callback.audio_buffer = []
        audio_frame_callback.audio_buffer.append(frame.to_ndarray().tobytes())
        return frame

    webrtc_ctx = webrtc_streamer(
        key="voice-input",
        mode=WebRtcMode.SENDONLY,  # ✅ Correct enum usage
        audio_frame_callback=audio_frame_callback,
        media_stream_constraints={"audio": True, "video": False},
        async_processing=True
    )

    if webrtc_ctx.state.playing is False and hasattr(audio_frame_callback, "audio_buffer"):
        try:
            audio_data = b"".join(audio_frame_callback.audio_buffer)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                st.session_state.audio_file_path = f.name
                st.session_state.audio_ready = True
                st.success("✅ Audio captured!")
        except Exception as e:
            st.error(f"Error saving audio: {e}")
        finally:
            del audio_frame_callback.audio_buffer

    if st.session_state.audio_ready and st.session_state.audio_file_path:
        if st.button("🔎 Process Voice Input"):
            r = sr.Recognizer()
            try:
                with sr.AudioFile(st.session_state.audio_file_path) as source:
                    audio_data = r.record(source)
                    st.session_state.spoken_text = r.recognize_google(audio_data)
                    st.success(f"🎤 Transcription: {st.session_state.spoken_text}")
            except sr.UnknownValueError:
                st.warning("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                st.error(f"Could not request results from Google Speech Recognition service; {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

# --- Add Item Form ---
st.header("📦 Add New Item (with optional voice input)")

with st.form("add_item"):
    item_name = st.text_input("Item Name", value=st.session_state.spoken_text)
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
    results = [row for row in records if search_query.lower() in str(row["Item Name"]).lower()]
    if results:
        st.write(f"Found {len(results)} result(s):")
        st.table(results)
    else:
        st.warning("Item not found.")
