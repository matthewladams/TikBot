import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil

import yt_dlp
from yt_dlp.utils import DownloadError

from dbInteraction import doesPostExist

logger = logging.getLogger(__name__)


def _get_format_candidates(video_url: str) -> list[str]:
    """Return an ordered list of format strings to try for the given URL."""
    lowered_url = video_url.lower()
    candidates: list[str] = []

    if 'twitch.tv' in lowered_url:
        candidates.append('best[filesize<8M][format_id!*=portrait]/worst[format_id!*=portrait]')
    else:
        candidates.append('best[filesize<8M]/worst')

    if 'reddit.com' in lowered_url:
        # Reddit often provides separate audio/video streams. Fallback to merging them.
        candidates.append('bv*+ba/b')

    if 'best' not in candidates:
        candidates.append('best')

    return candidates


def _create_ydl_opts(format_selection: str) -> dict:
    """Create yt-dlp options for a download attempt."""
    opts: dict[str, object] = {
        'format': format_selection,
        'outtmpl': '%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'logger': logger,
    }

    # Preserve existing sorting preference where it makes sense.
    if 'filesize' in format_selection:
        opts['format_sort'] = ['+filesize', '+codec:h264']
    else:
        opts['format_sort'] = ['+codec:h264']

    # Enable remote-components support (EJS from npm) when a compatible JS runtime
    # is available (Deno or Bun) or when explicitly requested via environment.
    # This corresponds to passing --remote-components ejs:npm to yt-dlp.
    try:
        enable_remote = os.getenv('TIKBOT_ENABLE_REMOTE_COMPONENTS')
        has_runtime = shutil.which('deno') is not None or shutil.which('bun') is not None
        if (enable_remote and enable_remote.lower() in ('1', 'true', 'yes')) or has_runtime:
            opts['remote_components'] = ['ejs:github']
            logger.info("Enabled yt-dlp remote_components='ejs:github' (has_runtime=%s, env=%s)", has_runtime, enable_remote)
    except Exception:
        # Don't fail if shutil or env checks misbehave for any reason
        logger.error('Could not determine JS runtime availability for remote components', exc_info=True)

    return opts


def download(videoUrl: str, detect_repost: bool = True):
    response = {
        'fileName': '',
        'duration': 0,
        'messages': '',
        'videoId': '',
        'repost': False,
        'repostOriginalMesssageId': '',
        'attemptedFormats': [],
        'selectedFormat': None,
        'lastError': None,
    }

    logger.info("Starting download for url %s", videoUrl)

    result = None
    attempted_formats = []
    last_exception: Exception | None = None
    selected_format: str | None = None

    for format_selection in _get_format_candidates(videoUrl):
        attempted_formats.append(format_selection)
        ydl_opts = _create_ydl_opts(format_selection)
        logger.debug("Attempting download with format '%s' for url %s", format_selection, videoUrl)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(videoUrl, download=True)
                logger.info("Download succeeded with format '%s' for url %s", format_selection, videoUrl)
                selected_format = format_selection
                last_exception = None
                break
        except DownloadError as ex:
            logger.warning("Download attempt with format '%s' for url %s failed: %s", format_selection, videoUrl, ex)
            last_exception = ex
        except Exception as ex:  # Catch-all to ensure retries on unexpected errors.
            logger.error("Unexpected error during download with format '%s' for url %s: %s", format_selection, videoUrl, ex)
            last_exception = ex

    if result is None:
        if last_exception:
            logger.error(
                "All download attempts failed for url %s. Tried formats: %s",
                videoUrl,
                attempted_formats,
                exc_info=(type(last_exception), last_exception, last_exception.__traceback__)
            )
            response['lastError'] = str(last_exception)
        response['messages'] = 'Error: Download Failed'
        response['attemptedFormats'] = attempted_formats
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

    if detect_repost:
        try:
            # TODO - get the platform for this not just be lazy
            reposted = doesPostExist(video['id'], 'MattIsLazy')
            if reposted is not None:
                logger.debug("Trying repost detection with response %s", reposted)
                repostUserId = reposted[0]
                logger.debug("Got repost user id %s", repostUserId)
                repostTime = reposted[1]
                repostTimeTimezone = datetime_from_utc_to_local(repostTime)
                if repostUserId != '':
                    response['messages'] = f'This is a repost! Originally posted at {repostTimeTimezone.strftime("%d/%m/%Y %H:%M:%S")}'
                    response['repost'] = True
                    response['repostOriginalMesssageId'] = reposted[2]
        except Exception as e:
            # Don't die for repost detection
            logger.error("Exception trying to do repost detection", exc_info=(type(e), e, e.__traceback__))

    response['attemptedFormats'] = attempted_formats
    response['selectedFormat'] = selected_format
    response['lastError'] = str(last_exception) if last_exception else None

    return response

def _list_from_options_callback(option, value, parser, append=True, delim=',', process=str.strip):
    # append can be True, False or -1 (prepend)
    current = getattr(parser.values, option.dest) if append else []
    value = list(filter(None, [process(value)] if delim is None else map(process, value.split(delim))))
    setattr(
        parser.values, option.dest,
        current + value if append is True else value + current)

def datetime_from_utc_to_local(utc_datetime: datetime):
    timezone = os.getenv('TIKBOT_TIMEZONE') or 'UTC'
    return utc_datetime.astimezone(tz=ZoneInfo(timezone))
