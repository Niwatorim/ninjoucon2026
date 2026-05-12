import yt_dlp

url = 'https://www.youtube.com/watch?v=GJ_GdMc19eg'
ydl_opts = {
    'format': 'bestvideo+bestaudio/best', 
    'outtmpl': '%(title)s.%(ext)s',
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
