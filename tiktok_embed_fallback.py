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
                if (
                    _is_tiktok_media_url(url, video_id)
                    and (
                        resource_type == "media"
                        or (resource_type in ("xhr", "fetch") and "video" in content_type)
                        or ".mp4" in url
                    )
                ):
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
                        _is_tiktok_media_url(resp.url, video_id)
                        and (
                            "video" in resp.headers.get("content-type", "")
                            or ".mp4" in resp.url
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
            if media_response["response"] is None:
                html_snapshot = page.content()
                try:
                    video_url = page.evaluate(
                        """() => {
                            const video = document.querySelector('video');
                            if (video && video.src) return video.src;
                            const source = document.querySelector('video source');
                            if (source && source.src) return source.src;
                            const script = document.querySelector('#__FRONTITY_CONNECT_STATE__');
                            if (!script) return null;
                            try {
                                const state = JSON.parse(script.textContent || '{}');
                                const data = state?.source?.data || {};
                                for (const key of Object.keys(data)) {
                                    const videoData = data[key]?.videoData;
                                    const urls = videoData?.itemInfos?.video?.urls;
                                    if (urls && urls.length) return urls[0];
                                }
                            } catch (e) {
                                return null;
                            }
                            return null;
                        }"""
                    )
                except Exception:
                    video_url = None

                if video_url:
                    logger.info("Playwright extracted video url from DOM/state: %s", video_url)
                    try:
                        body = page.evaluate(
                            """async (url) => {
                                const response = await fetch(url);
                                if (!response.ok) {
                                    return { ok: false, status: response.status };
                                }
                                const buffer = await response.arrayBuffer();
                                const bytes = new Uint8Array(buffer);
                                return { ok: true, bytes: Array.from(bytes) };
                            }""",
                            video_url,
                        )
                        if isinstance(body, dict) and body.get("ok") and body.get("bytes"):
                            with open(output_name, "wb") as handle:
                                handle.write(bytes(body["bytes"]))
                            download_result = {
                                "video_id": video_id or "",
                                "download_url": video_url,
                                "embed_url": page_url,
                                "file_path": output_name,
                            }
                        else:
                            status = body.get("status") if isinstance(body, dict) else None
                            logger.info("Playwright in-page fetch failed (status=%s)", status)
                    except Exception as exc:
                        logger.warning("Playwright in-page fetch failed: %s", exc)
            if media_response["response"] is not None and download_result is None:
                try:
                    body = media_response["response"].body()
                    with open(output_name, "wb") as handle:
                        handle.write(body)
                    download_result = {
                        "video_id": video_id or "",
                        "download_url": media_response["response"].url,
                        "embed_url": page_url,
                        "file_path": output_name,
                    }
                except Exception as exc:
                    logger.warning("Failed to save Playwright media response: %s", exc)
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

    try:
        body = response.body()
        with open(output_name, "wb") as handle:
            handle.write(body)
    except Exception as exc:
        logger.warning("Failed to save Playwright media response: %s", exc)
        return None

    return {
        "video_id": video_id or "",
        "download_url": response.url,
        "embed_url": page_url,
        "file_path": output_name,
    }
