import asyncio
import json
import logging
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_TIKTOK_VIDEO_ID_RE = re.compile(r"/(?:video|photo)/(?P<id>\d+)")
_TIKTOK_EMBED_ID_RE = re.compile(r"/embed/v2/(?P<id>\d+)")
_VIDEO_URL_HINTS = (".mp4", ".mov", ".m4v", ".webm")
_SUBTITLE_URL_HINTS = (".vtt", ".srt", ".ass", ".ttml", ".dfxp")
_SUBTITLE_CONTENT_TYPES = (
    "text/vtt",
    "application/x-subrip",
    "application/ttml+xml",
    "application/cea-608",
    "application/cea-708",
)
_HTML_URL_RE = re.compile(r'https://[^"\'<>\s]+')


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


def _extract_tiktok_embed_id(url: str) -> str | None:
    match = _TIKTOK_EMBED_ID_RE.search(url)
    if match:
        return match.group('id')
    return None


def _is_tiktok_media_url(url: str, video_id: str | None) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "ttwstatic.com" in host:
        return False
    if "tiktokcdn.com" in host or "/video/tos/" in parsed.path or "tiktok.com/video/" in url:
        return True
    if video_id:
        return video_id in url or f"item_id={video_id}" in url or f"__vid={video_id}" in url
    return False


def _normalized_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _is_subtitle_like_url(url: str) -> bool:
    lowered_url = url.lower()
    return any(hint in lowered_url for hint in _SUBTITLE_URL_HINTS) or any(
        marker in lowered_url for marker in (
            "subtitle",
            "captions",
            "caption",
            "format=webvtt",
            "captionformat=webvtt",
            "big_caption",
        )
    )


def _is_video_like_url(url: str) -> bool:
    lowered_url = url.lower()
    return any(hint in lowered_url for hint in _VIDEO_URL_HINTS) or "/video/tos/" in lowered_url


def _is_downloadable_tiktok_video_response(
    url: str,
    content_type: str | None,
    resource_type: str | None,
    video_id: str | None,
) -> bool:
    normalized_content_type = _normalized_content_type(content_type)
    normalized_resource_type = (resource_type or "").lower()

    if not _is_tiktok_media_url(url, video_id):
        return False
    if _is_subtitle_like_url(url):
        return False
    if normalized_content_type in _SUBTITLE_CONTENT_TYPES or "vtt" in normalized_content_type:
        return False
    if normalized_content_type.startswith("video/"):
        return True
    if _is_video_like_url(url):
        return normalized_content_type in ("", "application/octet-stream") or normalized_resource_type in (
            "media",
            "xhr",
            "fetch",
        )
    return False


def _looks_like_webvtt_payload(payload: bytes) -> bool:
    sample = payload.lstrip(b"\xef\xbb\xbf\r\n\t ")
    return sample.startswith(b"WEBVTT")


def _looks_like_video_payload(payload: bytes) -> bool:
    header = payload[:64]
    return (
        b"ftyp" in header
        or header.startswith(b"\x1a\x45\xdf\xa3")
        or header.startswith(b"OggS")
    )


def _extract_tiktok_media_urls_from_html(html: str, video_id: str | None) -> list[str]:
    normalized_html = html.replace("\\u002F", "/").replace("\\/", "/")
    seen: set[str] = set()
    candidates: list[str] = []

    for url in _HTML_URL_RE.findall(normalized_html):
        lowered_url = url.lower()
        if url in seen:
            continue
        if not (
            "/video/tos/" in lowered_url
            or "/aweme/v1/play/" in lowered_url
            or "mime_type=video_mp4" in lowered_url
        ):
            continue
        if video_id and video_id not in url and f"item_id={video_id}" not in lowered_url:
            continue
        seen.add(url)
        candidates.append(url)

    return candidates


def _download_candidate_url(
    download_url: str,
    output_path: str,
    referer: str,
) -> bool:
    try:
        request = urllib.request.Request(
            download_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": referer,
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            first_chunk = response.read(4096)
            content_type = response.headers.get("Content-Type", "")
            if not first_chunk:
                logger.info("TikTok candidate returned no body bytes: %s", download_url)
                return False
            if _looks_like_webvtt_payload(first_chunk):
                logger.info(
                    "Rejected TikTok candidate with WEBVTT payload (content_type=%s): %s",
                    content_type,
                    download_url,
                )
                return False
            if not _looks_like_video_payload(first_chunk):
                logger.info(
                    "Rejected TikTok candidate that did not look like media bytes (content_type=%s): %s",
                    content_type,
                    download_url,
                )
                return False

            with open(output_path, "wb") as handle:
                handle.write(first_chunk)
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    handle.write(chunk)
        return True
    except Exception as exc:
        logger.info("Failed to fetch TikTok candidate %s: %s", download_url, exc)
        return False


def get_tiktok_video_page_url(video_url: str) -> str | None:
    if "/video/" in video_url:
        return video_url
    host = _extract_host(video_url)
    if host in ('vm.tiktok.com', 'vt.tiktok.com'):
        resolved_url = _resolve_tiktok_short_url(video_url)
        if resolved_url:
            return resolved_url
    return None


def download_tiktok_embed_video_playwright(
    video_url: str,
    output_path: str | None = None,
    timeout_ms: int = 20000,
) -> dict | None:
    try:
        asyncio.get_running_loop()
        in_event_loop = True
    except RuntimeError:
        in_event_loop = False

    if in_event_loop:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_download_tiktok_playwright_sync, video_url, output_path, timeout_ms)
            return future.result()

    return _download_tiktok_playwright_sync(video_url, output_path, timeout_ms)


def _download_tiktok_playwright_sync(
    video_url: str,
    output_path: str | None,
    timeout_ms: int,
) -> dict | None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        logger.info("Playwright not available for TikTok download: %s", exc)
        return None

    page_url = get_tiktok_video_page_url(video_url) or get_tiktok_embed_url(video_url)
    if not page_url:
        return None

    video_id = _extract_tiktok_embed_id(page_url) or _extract_tiktok_video_id(page_url)
    output_name = output_path or (f"{video_id}.mp4" if video_id else "tiktok.mp4")
    logger.info("Attempting TikTok download via Playwright at %s", page_url)

    media_response = {"response": None, "count": 0}
    response_samples: list[tuple[str, str, str]] = []
    html_snapshot = None
    download_result = None
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            logger.warning("Playwright Chromium launch failed: %s", exc)
            return None
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            media_response["count"] += 1
            if media_response["response"] is not None:
                return
            try:
                resource_type = response.request.resource_type
                content_type = response.headers.get("content-type", "")
                url = response.url
                if _is_downloadable_tiktok_video_response(url, content_type, resource_type, video_id):
                    media_response["response"] = response
                elif len(response_samples) < 15:
                    response_samples.append((resource_type, content_type, url))
            except Exception:
                return

        page.on("response", handle_response)

        try:
            logger.info("Playwright navigating to %s", page_url)
            page.goto(page_url, wait_until="networkidle", timeout=timeout_ms)
            try:
                played = page.evaluate(
                    """() => {
                        const video = document.querySelector('video');
                        if (!video) return false;
                        video.muted = true;
                        return video.play().then(() => true).catch(() => false);
                    }"""
                )
                logger.info("Playwright attempted video.play()=%s", played)
            except Exception as exc:
                logger.info("Playwright could not start video playback: %s", exc)
            try:
                response = page.wait_for_response(
                    lambda resp: (
                        _is_downloadable_tiktok_video_response(
                            resp.url,
                            resp.headers.get("content-type", ""),
                            resp.request.resource_type,
                            video_id,
                        )
                    ),
                    timeout=timeout_ms,
                )
                media_response["response"] = response
            except Exception:
                pass
            deadline = time.time() + (timeout_ms / 1000.0)
            while media_response["response"] is None and time.time() < deadline:
                page.wait_for_timeout(250)
            candidate_urls: list[str] = []
            if media_response["response"] is not None:
                candidate_urls.append(media_response["response"].url)

            try:
                dom_urls = page.evaluate(
                    """() => {
                        const urls = [];
                        const push = (value) => {
                            if (typeof value === 'string' && value) urls.push(value);
                        };
                        const video = document.querySelector('video');
                        if (video) {
                            push(video.currentSrc);
                            push(video.src);
                        }
                        const source = document.querySelector('video source');
                        if (source) push(source.src);
                        return urls;
                    }"""
                )
            except Exception:
                dom_urls = []

            if isinstance(dom_urls, list):
                candidate_urls.extend(url for url in dom_urls if isinstance(url, str))

            html_snapshot = page.content()
            candidate_urls.extend(_extract_tiktok_media_urls_from_html(html_snapshot, video_id))

            deduped_candidate_urls: list[str] = []
            seen_urls: set[str] = set()
            for candidate_url in candidate_urls:
                if not isinstance(candidate_url, str):
                    continue
                if candidate_url in seen_urls:
                    continue
                seen_urls.add(candidate_url)
                deduped_candidate_urls.append(candidate_url)

            for candidate_url in deduped_candidate_urls:
                if _is_subtitle_like_url(candidate_url):
                    logger.info("Skipping subtitle-like TikTok candidate url: %s", candidate_url)
                    continue
                if _download_candidate_url(candidate_url, output_name, page_url):
                    download_result = {
                        "video_id": video_id or "",
                        "download_url": candidate_url,
                        "embed_url": page_url,
                        "file_path": output_name,
                    }
                    break
        except Exception as exc:
            logger.warning("Playwright failed to load TikTok embed page: %s", exc)
        finally:
            page.close()
            context.close()
            browser.close()

    if download_result:
        return download_result

    response = media_response["response"]
    if response is None:
        logger.info(
            "Playwright did not observe a media response for %s (responses_seen=%s)",
            page_url,
            media_response["count"],
        )
        for resource_type, content_type, url in response_samples:
            logger.info("Playwright response sample type=%s content_type=%s url=%s", resource_type, content_type, url)
        return None
    if not response.ok:
        logger.info("Playwright media response failed for %s (status=%s)", page_url, response.status)
        return None

    logger.info("Playwright observed media response but found no valid downloadable video candidate for %s", page_url)
    return None
