import logging
import os
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DownloadError

from dbInteraction import doesPostExist
from validator import normalize_platform
from tiktok_embed_fallback import download_tiktok_embed_video_playwright, get_tiktok_embed_url

logger = logging.getLogger(__name__)

class _YtdlpLogger:
    def __init__(self, base_logger: logging.Logger):
        self._logger = base_logger

    def debug(self, msg):
        self._logger.debug("yt-dlp: %s", msg)

    def info(self, msg):
        self._logger.info("yt-dlp: %s", msg)

    def warning(self, msg):
        self._logger.warning("yt-dlp: %s", msg)

    def error(self, msg):
        # Avoid double-reporting errors; DownloadError already surfaces them.
        self._logger.debug("yt-dlp error: %s", msg)


_YTDLP_LOGGER = _YtdlpLogger(logger)


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
        'no_warnings': True,
        'logger': _YTDLP_LOGGER,
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

    impersonate = os.getenv('TIKBOT_IMPERSONATE')
    if impersonate:
        try:
            normalized = impersonate.strip().lower()
            opts['impersonate'] = ImpersonateTarget.from_str(normalized)
            logger.info("Enabled yt-dlp impersonation=%s", normalized)
        except ValueError as exc:
            logger.warning("Invalid TIKBOT_IMPERSONATE value '%s': %s", impersonate, exc)

    return opts


def _compact_error_message(error: Exception) -> str:
    message = str(error).replace("ERROR: ", "").strip()
    marker = "please report this issue"
    lower_message = message.lower()
    if marker in lower_message:
        cutoff = lower_message.index(marker)
        message = message[:cutoff].rstrip(" ;.")
    return message.splitlines()[0] if message else "unknown error"


def _attempt_download(video_url: str, attempted_formats: list[str], label: str | None = None):
    result = None
    last_exception: Exception | None = None
    selected_format: str | None = None

    for format_selection in _get_format_candidates(video_url):
        reported_format = f"{format_selection} ({label})" if label else format_selection
        attempted_formats.append(reported_format)
        ydl_opts = _create_ydl_opts(format_selection)
        logger.debug("Attempting download with format '%s' for url %s", format_selection, video_url)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(video_url, download=True)
                logger.info("Download succeeded with format '%s' for url %s", format_selection, video_url)
                selected_format = reported_format
                last_exception = None
                break
        except DownloadError as ex:
            logger.warning(
                "Download attempt failed (format=%s, label=%s): %s",
                format_selection,
                label or "direct",
                _compact_error_message(ex),
            )
            last_exception = ex
        except Exception as ex:  # Catch-all to ensure retries on unexpected errors.
            logger.error("Unexpected error during download with format '%s' for url %s: %s", format_selection, video_url, ex)
            last_exception = ex

    return result, selected_format, last_exception


def _resolve_downloaded_filepath(video: dict) -> str | None:
    requested_downloads = video.get('requested_downloads') or []
    if requested_downloads:
        filepath = requested_downloads[0].get('filepath') or requested_downloads[0].get('filename')
        if filepath:
            return filepath
    filepath = video.get('_filename')
    if filepath:
        return filepath
    if video.get('id'):
        return f"{video['id']}.mp4"
    return None


def _normalize_downloaded_extension(video: dict, filepath: str) -> str:
    ext = None
    requested_downloads = video.get('requested_downloads') or []
    if requested_downloads:
        ext = requested_downloads[0].get('ext')
    ext = ext or video.get('ext')

    if ext in (None, '', 'unknown_video') and filepath.endswith('.unknown_video'):
        renamed = filepath.rsplit('.', 1)[0] + '.mp4'
        try:
            os.replace(filepath, renamed)
            logger.info("Renamed %s to %s based on unknown_video extension", filepath, renamed)
            return renamed
        except OSError as exc:
            logger.warning("Failed to rename %s to %s: %s", filepath, renamed, exc)
            return filepath

    return filepath


def download(videoUrl: str, detect_repost: bool = True):
    response = {
        'fileName': '',
        'duration': 0,
        'messages': '',
        'videoId': '',
        'platform': normalize_platform(videoUrl),
        'repost': False,
        'repostOriginalMesssageId': '',
        'attemptedFormats': [],
        'selectedFormat': None,
        'lastError': None,
    }

    logger.info("Starting download for url %s", videoUrl)
    if response['platform'] == 'tiktok' and not os.getenv('TIKBOT_IMPERSONATE'):
        logger.info(
            "TikTok downloads often require yt-dlp impersonation; set TIKBOT_IMPERSONATE=chrome-120 or similar "
            "(see `python -m yt_dlp --list-impersonate-targets`)"
        )

    attempted_formats = []
    download_method = "yt-dlp"
    result, selected_format, last_exception = _attempt_download(videoUrl, attempted_formats)

    if result is None and response['platform'] == 'tiktok':
        embed_url = get_tiktok_embed_url(videoUrl)
        if embed_url:
            logger.info("Direct TikTok download failed; retrying with embed URL %s", embed_url)
            download_method = "yt-dlp-embed"
            result, selected_format, last_exception = _attempt_download(
                embed_url,
                attempted_formats,
                label='embed'
            )
        if result is None:
            attempted_formats.append("embed-playwright")
            logger.info("Attempting TikTok download via Playwright fallback")
            download_result = download_tiktok_embed_video_playwright(videoUrl)
            if download_result:
                result = {
                    "id": download_result.get("video_id") or "",
                    "_filename": download_result["file_path"],
                }
                selected_format = "embed-playwright"
                download_method = "playwright"
                last_exception = None
            else:
                logger.warning("Playwright fallback did not produce a downloadable media response")
                last_exception = last_exception or Exception("Playwright embed download failed")

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
    response['videoId'] = video['id']

    downloaded_filepath = _resolve_downloaded_filepath(video)
    if not downloaded_filepath or not os.path.exists(downloaded_filepath):
        response['messages'] = 'Error: Download Failed'
        response['attemptedFormats'] = attempted_formats
        response['selectedFormat'] = selected_format
        response['lastError'] = response['lastError'] or 'Downloaded file was not created'
        return response

    response['fileName'] = _normalize_downloaded_extension(video, downloaded_filepath)

    if detect_repost:
        try:
            reposted = doesPostExist(video['id'], response['platform'])
            if reposted is None and response['platform'] != 'unknown':
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

    if response['platform'] == 'tiktok':
        if response['messages']:
            response['messages'] = f"{response['messages']} (downloaded via {download_method})"
        else:
            response['messages'] = f"Info: Downloaded via {download_method}"

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
