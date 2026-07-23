"""
Input -> YouTube URL

Process : download YouTube video
Split into key poses
Check live camera

Output -> Switch keyposes forward or backward if user shows left or right point

Check keypose times, and make those time stamps:
if user matches that one, play to the next
"""
import json
import cv2
import websockets
import asyncio
import time
import os
import hashlib
import shutil

from utilities.youtube_downloader import downloader, start_extension_server, get_url_from_extension, get_checkpoint_boundary
from utilities.main_pipeline import interactive_training_session
from utilities.preprocess import generate_keyposes_new

async def main():
    # Start the extension background server to listen for URL and Checkpoint
    asyncio.create_task(start_extension_server())

    print("Waiting for URL from Chrome Extension...")
    url = await get_url_from_extension()
    
    # Keypose caching
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    cache_keyposes = f"keyposes/{url_hash}_keyposes.json"
    cache_timestamps = f"keyposes/{url_hash}_timestamps.json"

    if os.path.exists(cache_keyposes) and os.path.exists(cache_timestamps):
        print(f"Cache hit for URL hash {url_hash}, skipping download + generation.")
        shutil.copy(cache_keyposes, "./keyposes/teacher_keyposes.json")
        shutil.copy(cache_timestamps, "./keyposes/teacher_timestamps.json")
    else:
        print("downloading youtube video")
        video_filename = "./Teacher_video.webm" # Fallback if we download it (but I havent ggs)
        try:
            # keep WebSocket responsive
            video_filename = await asyncio.to_thread(downloader, url)
            print(f"Downloaded as: {video_filename}")
        except Exception as e:
            print(f"failed to download: {e}")

        print("Generating keyframes")
        try:
            await asyncio.to_thread(generate_keyposes_new, video_filename)
        except Exception as e:
            print(f"failed to generate keyframes: {e}")

        if os.path.exists("./keyposes/teacher_keyposes.json"):
            shutil.copy("./keyposes/teacher_keyposes.json", cache_keyposes)
        if os.path.exists("./keyposes/teacher_timestamps.json"):
            shutil.copy("./keyposes/teacher_timestamps.json", cache_timestamps)

        if os.path.exists(video_filename):
            os.remove(video_filename)

    #load time stamps:
    try:
        with open("./keyposes/teacher_timestamps.json","r") as f:
            timestamps = json.load(f)
    except FileNotFoundError:
        print("teacher_timestamps.json not found, make sure generate_keyposes worked.")
        timestamps = {}

    print("Video processed! Waiting for Checkpoint from Chrome Extension...")
    point = await get_checkpoint_boundary(timestamps)
    
    async def stream(websocket):
        print("Extension Connected to Pipeline!")
        video_name = url
        await interactive_training_session(websocket, timestamps, video_name, point)

    print("Starting pipeline websocket server on ws://localhost:8765")
    async with websockets.serve(stream, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
