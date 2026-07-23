import yt_dlp
import asyncio
import websockets
import json


def downloader(url:str) -> str:
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best', 
        'outtmpl': 'Teacher_video.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: #type: ignore
        info_dict = ydl.extract_info(url, download=True)
        if 'requested_downloads' in info_dict:
            filename = info_dict['requested_downloads'][0]['filepath']
        else:
            filename = ydl.prepare_filename(info_dict)
            
        return filename

url_future = None
checkpoint_future = None

async def extension_handler(websocket):
    global url_future, checkpoint_future
    print("="*50)
    print(" Extension Server running on ws://localhost:8000")
    print(" Waiting for 'Add Pipeline' and 'Save Checkpoint' from Chrome...")
    print("="*50)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "URL":
                    if url_future and not url_future.done():
                        print(f"\n[+] Received URL from Chrome: {data['url']}")
                        url_future.set_result(data['url'])
                elif data.get("type") == "CHECKPOINT":
                    if checkpoint_future and not checkpoint_future.done():
                        val = data["time"]
                        print(f"\n[+] Received Checkpoint Interval: {val}s")
                        checkpoint_future.set_result(val)
                elif data.get("type") == "CANCEL":
                    if checkpoint_future and not checkpoint_future.done():
                        print("\n[-] Checkpoint Cancelled by user. Proceeding without checkpoints.")
                        checkpoint_future.set_result("no")
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass

async def start_extension_server():
    async with websockets.serve(extension_handler, "localhost", 8000):
        await asyncio.Future()

async def get_url_from_extension():
    global url_future
    url_future = asyncio.Future()
    return await url_future

async def get_checkpoint_boundary(timestamps):
    global checkpoint_future
    checkpoint_future = asyncio.Future()
    checkpoint_interval = await checkpoint_future
    
    if checkpoint_interval == "no":
        checkpoint_interval = None
    
    if checkpoint_interval is not None and timestamps:
        chosen_key = "1"
        for key, val in sorted(timestamps.items(), key=lambda item: float(item[0])): # sort them, tho they shud be sorted
            
            #find last keypoint before the checkpoint
            if val <= checkpoint_interval:
                chosen_key = key
            else:
                break
        
        try:
            point = int(chosen_key)
            if point == 0:
                point = 1 #
        except ValueError:
            point = len(timestamps)
    else:
        point = len(timestamps)

    if checkpoint_interval is not None:
        print(f"Closest keypose to {checkpoint_interval}s is ID {point}. Using as checkpoint boundary.")
    else:
        print(f"No checkpoint set. Defaulting to full video (ID {point}).")
    
    return point
