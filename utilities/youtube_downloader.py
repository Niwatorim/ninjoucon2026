import yt_dlp


def downloader(url:str) -> str:
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best', 
        'outtmpl': 'Teacher_video.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: #type: ignore
        info_dict = ydl.extract_info(url, download=True)
        # Handle the dynamic extension yt-dlp might use (like .webm, .mkv, or .mp4)
        if 'requested_downloads' in info_dict:
            filename = info_dict['requested_downloads'][0]['filepath']
        else:
            filename = ydl.prepare_filename(info_dict)
            
        return filename
