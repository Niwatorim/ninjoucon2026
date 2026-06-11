import streamlit as st
import cv2
import os
import asyncio
import requests

st.set_page_config(page_title="Study Mode", layout="wide")
st.title("Learning mode")
st.header("Time to learn some moves!")
st.subheader("Viewing options:")
tab1, tab2 = st.tabs(["Teacher & User Live Camera", "Teacher & User 3D MoCap (Unity)"])

FLASK_BASE_URL = "http://localhost:5000/learn"

with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Teacher Feed")
        st.markdown(
            f'<img src="{FLASK_BASE_URL}/teacher_only" width="100%" style="border-radius: 8px;">',
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("### Your Live Camera")
        st.markdown(
            f'<img src="{FLASK_BASE_URL}/livecam_only" width="100%" style="border-radius: 8px;">',
            unsafe_allow_html=True,
        )
    
    st.divider()

    skip_button_1 = st.button("Skip keypose")
    if skip_button_1:
        try:
            # Send a POST request to the Flask server to update the state machine
            response = requests.post(f"{FLASK_BASE_URL}/skip_pose", timeout=2)
        
            if response.status_code == 200:
                # Briefly show a success message that automatically fades out
                st.toast("Pose skipped! Moving to the next one...", icon="✅")
            else:
                st.error(f"Failed to skip. Server returned status: {response.status_code}")
            
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the backend server. Is Flask running?")
        except requests.exceptions.Timeout:
            st.warning("The server took too long to respond.")


with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Teacher Feed")
        st.markdown(
            f'<img src="{FLASK_BASE_URL}/teacher_only" width="100%" style="border-radius: 8px;">',
            unsafe_allow_html=True,
        )
        
    with col2:
        st.markdown("### 3D MoCap (Unity)")
        st.markdown(
            f'<img src="{FLASK_BASE_URL}/unity_3dmocap_only" width="100%" style="border-radius: 8px;">',
            unsafe_allow_html=True,
        )
    
    st.divider()

    skip_button_2 = st.button("Skip keypose")
    if skip_button_2:
        try:
            # Send a POST request to the Flask server to update the state machine
            response = requests.post(f"{FLASK_BASE_URL}/skip_pose", timeout=2)
        
            if response.status_code == 200:
                # Briefly show a success message that automatically fades out
                st.toast("Pose skipped! Moving to the next one...", icon="✅")
            else:
                st.error(f"Failed to skip. Server returned status: {response.status_code}")
            
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the backend server. Is Flask running?")
        except requests.exceptions.Timeout:
            st.warning("The server took too long to respond.")


