# TikBot Agent Guide

## Purpose

TikBot is a small Python Discord bot that watches `tik-tok*` channels, downloads supported social video links, and reposts the media directly into Discord. If the file is too large or uses an inline-unfriendly codec, it re-encodes the video with `ffmpeg` before uploading it.

This repository is flat and script-oriented. There is no package directory, no build system, and no dependency lockfile.

## Entry Points

- `main.py`: Discord client entry point and message-processing flow.
- `downloader.py`: yt-dlp download logic, retry behavior, format selection, TikTok fallbacks, and repost detection integration.
- `tiktok_embed_fallback.py`: TikTok embed URL helpers and Playwright-based fallback downloader.
- `validator.py`: URL extraction, platform detection, supported-domain checks, and silent-mode logic.
- `calculator.py`: bitrate calculations used during compression.
- `dbInteraction.py`: optional Postgres-backed repost persistence.
- `tests.py`: both unit tests and live integration tests.
- `scripts/test_tiktok_playwright.py`: manual Playwright fallback smoke test.

## Runtime Requirements

- Python 3.9+ per `README.md`. The Docker image currently uses Python 3.14 slim.
- `ffmpeg` must be available on the host for audio conversion, probing, and compression.
- A Discord bot token in `.env` as `TOKEN=...` is required to run `main.py`.
- Playwright is optional, but TikTok fallback coverage is stronger when Chromium is installed.
- Postgres is optional. Without DB credentials, repost detection is disabled.
- Deno or Bun is optional. If either is present, yt-dlp remote components are enabled automatically in `downloader.py`.

## Useful Commands

Setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the bot:

```bash
python main.py
```

Run tests:

```bash
python -m pytest
```

Run only the fast/local tests with `unittest` patterns:

```bash
python -m pytest tests.py -k "not Integration"
```

Run the Playwright fallback smoke test:

```bash
python scripts/test_tiktok_playwright.py
```

Install Playwright Chromium if needed:

```bash
python -m playwright install chromium
```

## Environment Variables

Core:

- `TOKEN`: Discord bot token.
- `TIKBOT_LOG_LEVEL`: Python logging level. Defaults to `INFO`.
- `TIKBOT_FILE_SIZE_LIMIT`: Max upload size in MB. Defaults to `8`.
- `TIKBOT_RETRY_MULTI`: Retry backoff multiplier for downloads.

Download behavior:

- `TIKBOT_AUTO_DOMAINS`: Space-separated domains/platforms to auto-process.
- `TIKBOT_SILENT_DOMAINS`: Space-separated domains to attempt silently.
- `TIKBOT_IMPERSONATE`: yt-dlp impersonation target, important for TikTok reliability.
- `TIKBOT_ENABLE_REMOTE_COMPONENTS`: Forces yt-dlp remote components.
- `TIKBOT_ENABLE_PLAYWRIGHT`: Enables Playwright TikTok fallback.
- `TIKBOT_ENABLE_PLAYWRIGHT_TEST`: Enables the Playwright integration test in `tests.py`.

Repost detection:

- `DB_HOST`
- `DB_USER`
- `DB_PASS`
- `DB_NAME`
- `TIKBOT_TIMEZONE`

## Architecture Notes

- `main.py` owns Discord concerns: channel gating, DM audio conversion, retry notifications, and cleanup.
- `download_with_retries()` in `downloader.py` is the retry boundary. Prefer extending behavior there instead of re-implementing retries elsewhere.
- TikTok downloads use a cascading strategy:
  1. direct yt-dlp
  2. yt-dlp against the TikTok embed URL
  3. Playwright capture fallback
- Compression decisions live in `process_video()` and `send_compressed_video()` in `main.py`.
- Repost detection is optional but is wired into the downloader response model.

## Testing Notes

- `pytest.ini` points pytest at `tests.py`.
- `tests.py` contains both unit tests and live network integration tests. Expect Reddit/TikTok tests to hit the network unless skipped.
- GitHub Actions skips some Reddit integration coverage via `GITHUB_ACTIONS=true`.
- The Playwright integration test is opt-in via `TIKBOT_ENABLE_PLAYWRIGHT_TEST=1`.
- `temporary_working_directory()` currently preserves temp directories because `keep_tmp` is forced to `True`. Test runs may leave artifacts under `tmp_tests/`.

## Editing Guidance

- Keep changes small and script-friendly. The repo does not use classes or a framework-heavy structure outside the Discord client.
- Prefer touching existing modules instead of introducing abstraction layers unless the change clearly reduces risk.
- Be careful with import-time side effects:
  - `dbInteraction.py` attempts a Postgres connection at import time.
  - `main.py` loads `.env` at import time and constructs the Discord client globally.
- Preserve the current response contract from `download()` unless updating all call sites:
  - `fileName`
  - `duration`
  - `messages`
  - `videoId`
  - `platform`
  - `repost`
  - `repostOriginalMesssageId`
  - `attemptedFormats`
  - `selectedFormat`
  - `lastError`

## Validation Expectations

- For pure logic changes, run `python -m pytest`.
- For TikTok download-path changes, also run the relevant integration test or `python scripts/test_tiktok_playwright.py` when Playwright behavior is involved.
- For Discord message-flow changes, sanity-check `handleMessage()` in `main.py` for:
  - DM audio flow
  - `tik-tok*` channel gating
  - silent-mode handling
  - repost handling
  - cleanup of downloaded/compressed files

## Known Sharp Edges

- The README says Python 3.9+, but the Docker image is on Python 3.14. Avoid introducing syntax that unintentionally raises the local version floor.
- `dbInteraction.py` can print connection failures on import when DB env vars are absent.
- Network tests can fail for reasons unrelated to code changes, especially TikTok rate limiting, proxy issues, or temporary site behavior changes.
- TikTok support is brittle by nature. Prefer additive fallbacks and better diagnostics over deleting fallback paths.
