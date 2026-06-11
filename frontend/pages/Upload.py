import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from streamlit_option_menu import option_menu
import json
import yt_dlp
from streamlit_image_carousel import image_carousel


if "teacher_video" not in st.session_state:
    st.session_state.teacher_video=False

st.title("Add Teacher Video")
selected = option_menu(
        menu_title=None,  
        options=["Add Teacher Video", "Learn", "Playback"],  
        menu_icon="cast",  
        default_index=0, 
        orientation="horizontal",
    )

if selected== "Learn":
    st.switch_page("pages/Learn.py")
if selected == "Playback":
    st.switch_page("pages/Playback.py")

c1,c2=st.columns(2,gap="small")

with c1:
    st.header("Upload a video")
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "avi", "mkv"])

    st.divider()

    st.header("Download from Youtube")
    youtube_url = st.text_input("Give a Youtube URL")
    ydl_opts = {
    'format': 'bestvideo+bestaudio/best', 
    'outtmpl': '%(title)s.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        youtube_file = ydl.download([youtube_url])


with c2:
    if uploaded_file is not None:
        st.subheader("Uploaded video:")
        st.video(uploaded_file)
    if youtube_file is not None:
        st.subheader("Uploaded video:")
        st.video(youtube_file)
    
st.divider()
if uploaded_file is not None or youtube_file is not None:
    keyposes = st.button("Generate Teacher Keyposes")
    if keyposes:
        keypose_images = [
        "https://example.com",
        "https://example.com"
        ] #TODO: file paths to the generated teacher keyposes here
        image_carousel(image_urls=keypose_images, display_as_slider=True, width=700)

