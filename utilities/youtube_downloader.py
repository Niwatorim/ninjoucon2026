import yt_dlp
import asyncio
import websockets


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

async def wait_for_extension():
    stop_future = asyncio.Future()
    checkpoint_interval = None
    
    async def time_handler(websocket):
        nonlocal checkpoint_interval
        print("="*50)
        print(" Waiting for Chrome Extension Checkpoint Time on ws://localhost:8000")
        print(" Please use the slider on YouTube and click 'Save Checkpoint'.")
        print("="*50)
        try:
            async for message in websocket:
                if message == "no":
                    print("[-] Checkpoint Cancelled by user. Proceeding without checkpoints.")
                    stop_future.set_result(True)
                    break
                else:
                    try:
                        time_val = float(message)
                        print(f"\n[+] Received Checkpoint Interval: {time_val}s\n")
                        checkpoint_interval = time_val
                        stop_future.set_result(True)
                        break
                    except ValueError:
                        pass
        except websockets.exceptions.ConnectionClosed:
            pass

    async with websockets.serve(time_handler, "localhost", 8000):
        await stop_future
        
    return checkpoint_interval

async def get_checkpoint_boundary(timestamps):
    checkpoint_interval = await wait_for_extension()
    
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
