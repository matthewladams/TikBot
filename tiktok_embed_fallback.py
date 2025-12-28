import logging
import re
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_TIKTOK_VIDEO_ID_RE = re.compile(r"/(?:video|photo)/(?P<id>\d+)")


def _extract_host(url: str) -> str:
    normalized = url if '://' in url else f"https://{url}"
    parsed = urlparse(normalized)
    host = parsed.netloc or parsed.path.split('/')[0]
    host = host.split('@')[-1].split(':')[0]
    return host.lower()


def _extract_tiktok_video_id(url: str) -> str | None:
    match = _TIKTOK_VIDEO_ID_RE.search(url)
    if match:
        return match.group('id')
    return None


def _resolve_tiktok_short_url(url: str) -> str | None:
    try:
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.geturl()
    except Exception as exc:
        logger.warning("Failed to resolve TikTok short URL %s: %s", url, exc)
        return None


def get_tiktok_embed_url(video_url: str) -> str | None:
    if 'tiktok.com/embed' in video_url:
        return None

    video_id = _extract_tiktok_video_id(video_url)
    if not video_id:
        host = _extract_host(video_url)
        if host in ('vm.tiktok.com', 'vt.tiktok.com'):
            resolved_url = _resolve_tiktok_short_url(video_url)
            if resolved_url:
                video_id = _extract_tiktok_video_id(resolved_url)

    if not video_id:
        return None

    return f"https://www.tiktok.com/embed/v2/{video_id}"
