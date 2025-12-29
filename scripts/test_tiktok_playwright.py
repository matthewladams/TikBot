#!/usr/bin/env python
import logging
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
except Exception as exc:
    print(f"Playwright import failed: {exc}")
    print("Install with: python -m pip install playwright && python -m playwright install chromium")
    raise SystemExit(2)

from downloader import download


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://vt.tiktok.com/ZS58A5JDA/"
    os.environ["TIKBOT_ENABLE_PLAYWRIGHT"] = "1"

    logging.basicConfig(level=logging.INFO)
    print("Playwright enabled for TikTok download fallback")
    print("Ensuring Playwright Chromium is installed...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    try:
        response = download(url, detect_repost=False)
    except Exception as exc:
        message = str(exc)
        if "playwright install" in message or "Executable doesn't exist" in message:
            print("Playwright browser missing. Installing Chromium...")
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
            response = download(url, detect_repost=False)
        else:
            raise
    messages = response.get("messages") or ""
    if messages.startswith("Error"):
        last_error = response.get("lastError") or ""
        print(f"Download failed: {last_error}")
        return 1

    file_name = response.get("fileName")
    if file_name and os.path.exists(file_name):
        print(f"Downloaded to {file_name}")
    else:
        print(f"Download finished but file not found: {file_name}")
        return 1
    if messages:
        print(messages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
