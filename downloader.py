import yt_dlp
from dbInteraction import savePost, doesPostExist

def download(videoUrl):
    response = {'fileName':  '', 'duration':  0, 'messages': '', 'videoId': '', 'repost': False, 'repostOriginalMesssageId': ''}
    ydl = yt_dlp.YoutubeDL({'format_sort': ['+codec:h264'], 'outtmpl': '%(id)s.mp4', 'merge_output_format': 'mp4', 'user_agent': 'facebookexternalhit/1.1'})

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
    response['videoId'] = video['id']

    try:
        # TODO - get the platform for this not just be lazy
        reposted = doesPostExist(video['id'], 'MattIsLazy')
        # TODO use named accessors somehow
        if(reposted != None):
            print(f"trying repost detection with response {reposted}")
            repostUserId = reposted[0]
            print(f"got repost user id {repostUserId}")
            repostTime = reposted[1]
            if(repostUserId != ''):
                response['messages'] = f'This is a repost! Originally posted at {repostTime.strftime("%d/%m/%Y %H:%M:%S")}'
                response['repost'] = True
                response['repostOriginalMesssageId'] = reposted[2]
    except Exception as e:
        # Don't die for repost detection
        print(f"Exception trying to do repost detection: {e}")

    return response

def _list_from_options_callback(option, value, parser, append=True, delim=',', process=str.strip):
    # append can be True, False or -1 (prepend)
    current = getattr(parser.values, option.dest) if append else []
    value = list(filter(None, [process(value)] if delim is None else map(process, value.split(delim))))
    setattr(
        parser.values, option.dest,
        current + value if append is True else value + current)
