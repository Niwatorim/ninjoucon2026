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

#input youtube URL + download
from utilities.youtube_downloader import downloader

url = input("what is your youtube video? (type n to use already existing video): ")

# Keypose caching: hash URL and check for cached results
if url != "n":
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    cache_keyposes = f"keyposes/{url_hash}_keyposes.json"
    cache_timestamps = f"keyposes/{url_hash}_timestamps.json"

    if os.path.exists(cache_keyposes) and os.path.exists(cache_timestamps):
        print(f"Cache hit for URL hash {url_hash}, skipping download + generation.")
        shutil.copy(cache_keyposes, "./keyposes/teacher_keyposes.json")
        shutil.copy(cache_timestamps, "./keyposes/teacher_timestamps.json")
    else:


        print("downloading youtube video")
        video_filename = "./Teacher_video.webm" # Fallback
        try:
            video_filename = downloader(url)
            print(f"Downloaded as: {video_filename}")
        except Exception as e:
            print(f"failed to download: {e}")

        #split process into keyposes
        from utilities.preprocess import generate_keyposes_new
        print("Generating keyframes")
        try:
            generate_keyposes_new(video_filename)
        except Exception as e:
            print(f"failed to generate keyframes: {e}")

        # Copy generated files to cache for future reuse
        if os.path.exists("./keyposes/teacher_keyposes.json"):
            shutil.copy("./keyposes/teacher_keyposes.json", cache_keyposes)
        if os.path.exists("./keyposes/teacher_timestamps.json"):
            shutil.copy("./keyposes/teacher_timestamps.json", cache_timestamps)

        if os.path.exists(video_filename):
            os.remove(video_filename)

#------------ main loop -------------

#load time stamps:
try:
    with open("./keyposes/teacher_timestamps.json","r") as f:
        timestamps = json.load(f)
except FileNotFoundError:
    print("teacher_timestamps.json not found, make sure generate_keyposes worked.")
    timestamps = {}

#check checkpoints
import asyncio
import websockets
from utilities.main_pipeline import interactive_training_session
from utilities.youtube_downloader import get_checkpoint_boundary

async def main():
    point = await get_checkpoint_boundary(timestamps)
    
    async def stream(websocket):
        print("Extension Connected!")
        video_name = url
        await interactive_training_session(websocket, timestamps, video_name, point)

    print("Starting websocket server on ws://localhost:8765")
    async with websockets.serve(stream, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main()) #gets checkpoints
