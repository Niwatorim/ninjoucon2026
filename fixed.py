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

#input youtube URL + download
from utilities.youtube_downloader import downloader

url = input("what is your youtube video? (type n to use already existing video)")
if url != "n":
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


    #delete video to remove from memory
    os.remove("Teacher_video.webm")

#------------ main loop -------------

#load time stamps:
try:
    with open("./keyposes/teacher_timestamps.json","r") as f:
        timestamps = json.load(f)
except FileNotFoundError:
    print("teacher_timestamps.json not found, make sure generate_keyposes worked.")
    timestamps = {}

from utilities.main_pipeline import interactive_training_session

async def stream(websocket):
    print("Extension Connected!")
    video_name = url
    await interactive_training_session(websocket, timestamps, video_name)

async def main():
    print("Starting websocket server on ws://localhost:8765")
    server = await websockets.serve(stream, "localhost", 8765)
    await server.wait_closed()    

if __name__ == "__main__":
    asyncio.run(main())
