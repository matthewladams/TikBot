import youtube_dl

def download(videoUrl):
    response = {'fileName':  '', 'duration':  0, 'messages': ''}
    ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s.mp4'})


    with ydl:
        try:
            result = ydl.extract_info(
                videoUrl,
                download=True
            )
        except:
            response['messages'] = 'Error: Download Failed'
            return response

    if 'entries' in result:
        # Can be a playlist or a list of videos
        response['messages'] = 'Error: More than 1 result found. Please supply a single video only.'
        return response
    else:
        # Just a video
        video = result

    response['duration'] = video['duration']
    response['fileName'] = video['id'] + ".mp4"

    return response
