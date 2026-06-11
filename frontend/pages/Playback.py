import streamlit as st
import os
import json
import datetime
import requests

st.set_page_config(page_title="Playback Mode", layout="wide")
st.title("Playback Mode")

# --- 1. File System Logic ---
BASE_DIR = "./student_records"

# Ensure directory exists to prevent crashes
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

videos = os.listdir(BASE_DIR)

with st.sidebar:
    st.header("Session History")
    if not videos:
        st.warning("No recorded sessions found.")
        st.stop()
        
    selected_video = st.selectbox("Select Teacher Video", videos)
    
    # Get all timestamped sessions for this video
    video_path = os.path.join(BASE_DIR, selected_video)
    session_files = [f for f in os.listdir(video_path) if f.endswith('.json')]
    
    if not session_files:
        st.warning("No data found for this video.")
        st.stop()
        
    # Make the radio buttons readable (convert filename to readable date)
    session_options = {f: f.replace("session_", "").replace(".json", "") for f in session_files}
    selected_session_file = st.radio(
        "Select Training Time", 
        options=list(session_options.keys()), 
        format_func=lambda x: session_options[x]
    )

# --- 2. Load the Session Data ---
session_path = os.path.join(video_path, selected_session_file)
with open(session_path, "r") as f:
    session_data = json.load(f)

records = session_data.get("records", {})
pose_keys = list(records.keys())

st.header(f"Playback: {selected_video}")
st.subheader(f"Session from {session_options[selected_session_file]}")

# --- 3. Dynamic UI Generation ---
if not pose_keys:
    st.info("No keyposes recorded in this session.")
    st.stop()

st.text("Select keypose to review:")

# Manage state so clicking a button doesn't reset the radio button
if 'active_pose' not in st.session_state:
    st.session_state.active_pose = pose_keys[0]

# Create dynamic columns based on number of poses
cols = st.columns(len(pose_keys))
for idx, col in enumerate(cols):
    pose_name = pose_keys[idx]
    with col:
        if st.button(f"Pose {idx + 1}: {pose_name}", use_container_width=True):
            st.session_state.active_pose = pose_name

st.divider()

def trigger_unity_animation(session, pose):
    try:
        requests.post("http://localhost:5000/trigger_playback", json={
            "session": session,
            "pose": pose
        }, timeout=2)
    except requests.exceptions.RequestException as e:
        st.error("Could not connect to Flask backend to trigger animation.")

# Layout: Teacher Target (Left) | Unity Student Progress (Right)
col_teacher, col_student = st.columns(2)

with col_teacher:
    st.markdown("### Teacher Target Keypose")
    target_img_path = f"./keyposes/{st.session_state.active_pose}.png"
    if os.path.exists(target_img_path):
        st.image(target_img_path, use_container_width=True, caption="Correct Form")
    else:
        st.warning(f"Target image missing for {st.session_state.active_pose}")

with col_student:
    st.markdown("### Your Recorded Attempt (3D MoCap)")
    
    # Control buttons
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("▶ Replay Animation", use_container_width=True):
            trigger_unity_animation(selected_session_file, st.session_state.active_pose)
    with col_btn2:
        # Send an empty trigger to stop the thread
        if st.button("⏸ Stop", use_container_width=True):
            trigger_unity_animation(selected_session_file, "stop")

    # The video feed remains constant. It just shows whatever Unity is doing right now.
    st.markdown(
        '<img src="http://localhost:5000/unity_feed" width="100%" style="border-radius: 10px; border: 2px solid #2196F3;">',
        unsafe_allow_html=True,
    )
