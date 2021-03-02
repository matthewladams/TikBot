import youtube_dl

def download(videoUrl):
    ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s.mp4'})

    ydl_opts = {}

    with ydl:
        result = ydl.extract_info(
            videoUrl,
            download=True
        )

    if 'entries' in result:
        # Can be a playlist or a list of videos
        video = result['entries'][0]
        return "Error: More than 1 result found"
    else:
        # Just a video
        video = result

    print(video)
    video_url = video['title']
    videoId = video['id']

    return videoId + ".mp4"
