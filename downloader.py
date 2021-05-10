import youtube_dl

def download(videoUrl):
    response = {'fileName':  '', 'duration':  0, 'messages': ''}
    ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s.mp4', 'merge_output_format': 'mp4'})


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
        try:
            # Return just the first item
            video = result['entries'][0]
            # Can be a playlist or a list of videos
            if(len(result['entries']) > 1):
                response['messages'] = 'Info: More than 1 result found. Returning the first video found.'
        except:
            response['messages'] = 'Error: Download Failed - something went very poorly handling a playlist response.'
            return response
    else:
        # Just a video
        video = result

    if('duration' in video):
        response['duration'] = video['duration']
    response['fileName'] = video['id'] + ".mp4"

    return response
