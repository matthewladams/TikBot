import asyncio
import contextlib
import logging
import os
import tempfile
import unittest
import shutil
from unittest import mock

import downloader as downloader_module
import tiktok_embed_fallback as tiktok_fallback_module
from downloader import download_with_retries
from calculator import calculateBitrate, calculateBitrateAudioOnly
from validator import isSupportedUrl
from version import _get_version_from_git, get_status_label, get_status_text, get_version, get_version_label


if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("TIKBOT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

@contextlib.contextmanager
def temporary_working_directory():
    current = os.getcwd()
    base_tmp_dir = os.path.join(current, "tmp_tests")
    os.makedirs(base_tmp_dir, exist_ok=True)
    keep_tmp = os.getenv("TIKBOT_TEST_KEEP_TMP") == "1"
    keep_tmp = True
    tmpdir = tempfile.mkdtemp(dir=base_tmp_dir)
    os.chdir(tmpdir)
    try:
        yield tmpdir
    finally:
        os.chdir(current)
        if keep_tmp:
            logging.info("Keeping test temp dir: %s", tmpdir)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


def assert_download_succeeded(test_case, download_response, file_path, allow_zero_duration=False):
    if download_response["messages"] and download_response["messages"].startswith("Error"):
        last_error = download_response.get("lastError") or ""
        raise AssertionError(f"Download failed unexpectedly: {last_error}")

    test_case.assertTrue(os.path.exists(file_path))
    test_case.assertGreater(os.path.getsize(file_path), 0)
    if not allow_zero_duration:
        test_case.assertGreater(download_response["duration"], 0)
    else:
        if download_response["duration"] == 0:
            test_case.assertIn("downloaded via", download_response["messages"] or "")
    test_case.assertGreaterEqual(len(download_response["attemptedFormats"]), 1)
    test_case.assertIsNotNone(download_response["selectedFormat"])
    test_case.assertIn(download_response["selectedFormat"], download_response["attemptedFormats"])

class TestUrlParser(unittest.TestCase):

    def test_supportedUrl(self):
        url = "https://vt.tiktok.com/ZSrSTRC29/"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'true')

    def test_unsupportedUrl(self):
        url = "https://www.twitch.tv/robcdee/clip/AgileLivelyCucumberPartyTime"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'false')

IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"
PLAYWRIGHT_TEST_ENABLED = os.getenv("TIKBOT_ENABLE_PLAYWRIGHT_TEST") == "1"


class DownloaderTestCase(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._does_post_exist_patcher = mock.patch(
            'downloader.doesPostExist', autospec=True, return_value=None
        )
        self.mock_does_post_exist = self._does_post_exist_patcher.start()

    def tearDown(self):
        self._does_post_exist_patcher.stop()
        super().tearDown()


class _FakeChannel:
    def __init__(self, name="tik-tok-test"):
        self.sent = []
        self.name = name

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, "file": kwargs.get("file")})

    async def fetch_message(self, _message_id):
        return None


class _FakeAuthor:
    def __init__(self, name="test-user"):
        self.name = name


class _FakeMessage:
    def __init__(self, content=""):
        self.channel = _FakeChannel()
        self.author = _FakeAuthor()
        self.id = 1
        self.content = content


class TestMessageHandling(unittest.TestCase):

    def test_handleMessage_uses_repost_bypass_emoji(self):
        from main import handleMessage

        message = _FakeMessage("👾 https://www.tiktok.com/@test/video/123")
        download_response = {
            'fileName': '',
            'duration': 10,
            'messages': '',
            'videoId': '123',
            'platform': 'tiktok',
            'repost': False,
            'repostOriginalMesssageId': '',
        }

        with mock.patch("main.extractUrl", return_value={"url": "https://www.tiktok.com/@test/video/123", "messages": ""}):
            with mock.patch("main.isSupportedUrl", return_value={"supported": "true", "messages": "", "silentMode": False}):
                with mock.patch("main.download_with_retries", return_value=download_response) as mock_download:
                    with mock.patch("main.process_video", new=mock.AsyncMock()) as mock_process_video:
                        asyncio.run(handleMessage(message))

        mock_download.assert_called_once_with(
            "https://www.tiktok.com/@test/video/123",
            retries=4,
            on_retry=mock.ANY,
            detect_repost=False,
        )
        mock_process_video.assert_awaited_once()


class TestVersioning(unittest.TestCase):

    def test_get_version_uses_default_when_env_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("version._get_version_from_git", return_value=None):
                self.assertEqual(get_version(), "1.96.0")
                self.assertEqual(get_version_label(), "v1.96.0")

    def test_get_version_uses_git_commit_count_when_env_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("version._run_git_command", side_effect=[None, "96"]):
                self.assertEqual(_get_version_from_git(), "1.96.0")

    def test_get_status_text_uses_env_override(self):
        with mock.patch.dict(os.environ, {"TIKBOT_VERSION": "1.2.3"}):
            self.assertEqual(get_status_text(), "doomscrolling | v1.2.3")

    def test_get_status_text_keeps_existing_v_prefix(self):
        with mock.patch.dict(os.environ, {"TIKBOT_VERSION": "v2.0.0"}):
            self.assertEqual(get_status_text(), "doomscrolling | v2.0.0")

    def test_get_status_label_uses_env_override(self):
        with mock.patch.dict(os.environ, {"TIKBOT_STATUS_TEXT": "tik-tok channels"}):
            with mock.patch("version.get_version_label", return_value="v9.9.9"):
                self.assertEqual(get_status_label(), "tik-tok channels")
                self.assertEqual(get_status_text(), "tik-tok channels | v9.9.9")

    def test_get_version_prefers_exact_git_tag(self):
        with mock.patch("version._run_git_command", side_effect=["v1.120.0"]):
            self.assertEqual(_get_version_from_git(), "1.120.0")

    def test_on_ready_updates_presence_with_version(self):
        import main

        with mock.patch.dict(os.environ, {"TIKBOT_VERSION": "3.4.5"}):
            with mock.patch.object(main.client, "change_presence", new=mock.AsyncMock()) as mock_change_presence:
                asyncio.run(main.on_ready())

        mock_change_presence.assert_awaited_once()
        activity = mock_change_presence.await_args.kwargs["activity"]
        self.assertEqual(activity.name, "doomscrolling | v3.4.5")


@unittest.skipIf(IS_GITHUB_ACTIONS, "Reddit integration tests are blocked on GitHub Actions")
class TestDownloaderIntegration(DownloaderTestCase):

    REDDIT_URL = "https://www.reddit.com/r/justgalsbeingchicks/s/N7XkNUO9m4"
    TIKTOK_URL = "https://vt.tiktok.com/ZS58A5JDA/"
    TIKTOK_SHORT_URL = "https://vt.tiktok.com/ZS58vKJ4h/"

    def test_reddit_download_records_formats_and_saves_file(self):
        with temporary_working_directory() as tmpdir:
            download_response = download_with_retries(
                self.REDDIT_URL,
                retries=4,
                retry_multiplier=0,
                detect_repost=False
            )
            file_path = os.path.join(tmpdir, download_response["fileName"])

            if download_response["messages"] and download_response["messages"].startswith("Error"):
                last_error = download_response.get("lastError") or ""
                network_signals = (
                    "ProxyError",
                    "Tunnel connection failed",
                    "Temporary failure in name resolution",
                    "timed out",
                )
                if any(signal in last_error for signal in network_signals):
                    self.skipTest(f"Network unavailable for reddit download: {last_error}")
                self.fail(f"Reddit download failed unexpectedly: {last_error}")

            assert_download_succeeded(self, download_response, file_path)

        self.mock_does_post_exist.assert_not_called()

    def test_tiktok_download_records_formats_and_saves_file(self):
        with temporary_working_directory() as tmpdir:
            download_response = download_with_retries(
                self.TIKTOK_URL,
                retries=4,
                retry_multiplier=0,
                detect_repost=False
            )
            file_path = os.path.join(tmpdir, download_response["fileName"])

            if download_response["messages"] and download_response["messages"].startswith("Error"):
                last_error = download_response.get("lastError") or ""
                network_signals = (
                    "ProxyError",
                    "Tunnel connection failed",
                    "Temporary failure in name resolution",
                    "timed out",
                    "429",
                )
                if any(signal in last_error for signal in network_signals):
                    self.skipTest(f"Network unavailable for tiktok download: {last_error}")
                self.fail(f"TikTok download failed unexpectedly: {last_error}")

            assert_download_succeeded(self, download_response, file_path, allow_zero_duration=True)

        self.mock_does_post_exist.assert_not_called()

    def test_tiktok_short_url_download_records_formats_and_saves_file(self):
        with temporary_working_directory() as tmpdir:
            download_response = download_with_retries(
                self.TIKTOK_SHORT_URL,
                retries=4,
                retry_multiplier=0,
                detect_repost=False
            )
            file_path = os.path.join(tmpdir, download_response["fileName"])

            if download_response["messages"] and download_response["messages"].startswith("Error"):
                last_error = download_response.get("lastError") or ""
                network_signals = (
                    "ProxyError",
                    "Tunnel connection failed",
                    "Temporary failure in name resolution",
                    "timed out",
                    "429",
                )
                if any(signal in last_error for signal in network_signals):
                    self.skipTest(f"Network unavailable for tiktok download: {last_error}")
                self.fail(f"TikTok download failed unexpectedly: {last_error}")

            assert_download_succeeded(self, download_response, file_path, allow_zero_duration=True)

        self.mock_does_post_exist.assert_not_called()

    def test_tiktok_short_url_end_to_end_processing(self):
        from main import process_video

        with temporary_working_directory() as tmpdir:
            download_response = download_with_retries(
                self.TIKTOK_SHORT_URL,
                retries=4,
                retry_multiplier=0,
                detect_repost=False
            )
            file_path = os.path.join(tmpdir, download_response["fileName"])

            if download_response["messages"] and download_response["messages"].startswith("Error"):
                last_error = download_response.get("lastError") or ""
                network_signals = (
                    "ProxyError",
                    "Tunnel connection failed",
                    "Temporary failure in name resolution",
                    "timed out",
                    "429",
                )
                if any(signal in last_error for signal in network_signals):
                    self.skipTest(f"Network unavailable for tiktok download: {last_error}")
                self.fail(f"TikTok download failed unexpectedly: {last_error}")

            message = _FakeMessage()
            with mock.patch("main.savePost", autospec=True, return_value=None):
                try:
                    asyncio.run(
                        process_video(
                            message,
                            file_path,
                            download_response["duration"],
                            8_000_000,
                            download_response
                        )
                    )
                except Exception:
                    pass

            sent_text = [item["content"] for item in message.channel.sent if item["content"]]
            logging.info("E2E messages: %s", sent_text)
            logging.info("E2E selectedFormat: %s", download_response.get("selectedFormat"))
            failure_phrases = (
                "Failed to compress or send the video",
                "Failed to process the compressed video",
                "Failed to process the video file",
            )
            if any(phrase in text for text in sent_text for phrase in failure_phrases):
                self.fail(f"Compression failed in E2E flow: {sent_text}")
            self.assertTrue(
                any(item["file"] for item in message.channel.sent),
                f"Expected a file send, got: {sent_text}"
            )

    @unittest.skipUnless(PLAYWRIGHT_TEST_ENABLED, "Playwright test requires TIKBOT_ENABLE_PLAYWRIGHT_TEST=1")
    def test_tiktok_download_via_playwright(self):
        try:
            import playwright  # noqa: F401
        except Exception:
            self.skipTest("Playwright is not installed")

        original_enable = os.environ.get("TIKBOT_ENABLE_PLAYWRIGHT")
        os.environ["TIKBOT_ENABLE_PLAYWRIGHT"] = "1"
        try:
            with temporary_working_directory() as tmpdir:
                download_response = download_with_retries(
                    self.TIKTOK_URL,
                    retries=4,
                    retry_multiplier=0,
                    detect_repost=False
                )
                file_path = os.path.join(tmpdir, download_response["fileName"])

                if download_response["messages"]:
                    last_error = download_response.get("lastError") or ""
                    if "Playwright" in last_error or "browser" in last_error:
                        self.skipTest(f"Playwright unavailable: {last_error}")
                    self.fail(f"TikTok download failed unexpectedly: {last_error}")

                assert_download_succeeded(self, download_response, file_path, allow_zero_duration=True)
        finally:
            if original_enable is None:
                os.environ.pop("TIKBOT_ENABLE_PLAYWRIGHT", None)
            else:
                os.environ["TIKBOT_ENABLE_PLAYWRIGHT"] = original_enable

    def test_failed_download_reports_attempts(self):
        # Intentionally invalid video to trigger all fallbacks.
        url = "https://www.reddit.com/r/this_sub_does_not_exist/comments/abcdef/"

        with temporary_working_directory():
            download_response = download_with_retries(
                url,
                retries=4,
                retry_multiplier=0,
                detect_repost=False
            )

        self.assertEqual(download_response["messages"], 'Error: Download Failed')
        self.assertListEqual(
            download_response["attemptedFormats"],
            downloader_module._get_format_candidates(url)
        )
        self.assertIsNone(download_response["selectedFormat"])
        self.assertIsNotNone(download_response["lastError"])

        self.mock_does_post_exist.assert_not_called()

class TestCalculator(unittest.TestCase):

    def test_calculateBitrate_short_duration(self):
        """Test calculateBitrate with a short duration"""
        duration = 10  # 10 seconds
        result = calculateBitrate(duration)
        self.assertGreaterEqual(result.videoBitrate, 500)  # Minimum video bitrate
        self.assertGreaterEqual(result.audioBitrate, 32)  # Minimum audio bitrate
        self.assertLessEqual(result.audioBitrate, 320)  # Maximum audio bitrate
        self.assertFalse(result.durationLimited)

    def test_calculateBitrate_long_duration(self):
        """Test calculateBitrate with a long duration"""
        duration = 600  # 10 minutes
        result = calculateBitrate(duration)
        self.assertGreaterEqual(result.videoBitrate, 150)  # Minimum video bitrate
        self.assertGreaterEqual(result.audioBitrate, 32)  # Minimum audio bitrate
        self.assertLessEqual(result.audioBitrate, 320)  # Maximum audio bitrate
        self.assertTrue(result.durationLimited)

    def test_calculateBitrate_three_minute_clip_limit(self):
        """Test calculateBitrate keeps common 3-minute clips without truncation"""
        duration = 181
        result = calculateBitrate(duration)
        self.assertFalse(result.durationLimited)
        self.assertEqual(result.maxDuration, duration)

    def test_calculateBitrate_above_three_minute_clip_limit(self):
        """Test calculateBitrate truncates above the configured common 3-minute limit"""
        duration = 182
        result = calculateBitrate(duration)
        self.assertTrue(result.durationLimited)
        self.assertEqual(result.maxDuration, 181)

    def test_calculateBitrate_duration_limited(self):
        """Test calculateBitrate when duration is too long for quality"""
        duration = 10000  # Very long duration
        result = calculateBitrate(duration)
        self.assertEqual(result.videoBitrate, 260)
        self.assertEqual(result.audioBitrate, 64)
        self.assertLessEqual(result.audioBitrate, 320)  # Maximum audio bitrate
        self.assertTrue(result.durationLimited)

    def test_calculateBitrateAudioOnly_short_duration(self):
        """Test calculateBitrateAudioOnly with a short duration"""
        duration = 10  # 10 seconds
        result = calculateBitrateAudioOnly(duration)
        self.assertEqual(result.videoBitrate, 1)  # Video bitrate is fixed
        self.assertGreaterEqual(result.audioBitrate, 32)  # Minimum audio bitrate
        self.assertLessEqual(result.audioBitrate, 320)  # Maximum audio bitrate
        self.assertFalse(result.durationLimited)

    def test_calculateBitrateAudioOnly_long_duration(self):
        """Test calculateBitrateAudioOnly with a long duration"""
        duration = 600  # 10 minutes
        result = calculateBitrateAudioOnly(duration)
        self.assertEqual(result.videoBitrate, 1)  # Video bitrate is fixed
        self.assertGreaterEqual(result.audioBitrate, 32)  # Minimum audio bitrate
        self.assertLessEqual(result.audioBitrate, 320)  # Maximum audio bitrate
        self.assertFalse(result.durationLimited)

    def test_calculateBitrateAudioOnly_duration_limited(self):
        """Test calculateBitrateAudioOnly when duration is too long for quality"""
        duration = 10000  # Very long duration
        result = calculateBitrateAudioOnly(duration)
        self.assertEqual(result.videoBitrate, 1)  # Video bitrate is fixed
        self.assertGreaterEqual(result.audioBitrate, 32)  # Minimum audio bitrate
        self.assertLessEqual(result.audioBitrate, 320)  # Maximum audio bitrate
        self.assertFalse(result.durationLimited)

    def test_calculateBitrate_total_bitrate_limit(self):
        """Test that total bitrate * duration does not exceed 8 MB"""
        durations = [10, 30, 60, 200, 500, 1000]  # Short, long, and very long durations
        max_size = 8 * 1024 * 1024  # 8 MB in bytes

        for duration in durations:
            result = calculateBitrate(duration)
            total_bitrate = result.videoBitrate + result.audioBitrate  # in kbps
            total_size = (total_bitrate * 1000 / 8) * duration  # Convert kbps to bytes
            if(result.durationLimited == False):
                self.assertLessEqual(total_size, max_size, f"Exceeded 8 MB for duration {duration} and was not duration limited")

class TestDownloaderFormatSelection(DownloaderTestCase):

    def test_get_format_candidates_for_reddit(self):
        candidates = downloader_module._get_format_candidates("https://www.reddit.com/r/test/")
        self.assertEqual(
            candidates,
            ['best[filesize<8M]/worst', 'bv*+ba/b', 'best']
        )

    def test_get_format_candidates_for_twitch(self):
        candidates = downloader_module._get_format_candidates("https://www.twitch.tv/videos/123")
        self.assertEqual(
            candidates,
            ['best[filesize<8M][format_id!*=portrait]/worst[format_id!*=portrait]', 'best']
        )

    def test_get_format_candidates_for_youtube_short(self):
        candidates = downloader_module._get_format_candidates(
            "https://youtube.com/shorts/aSCz2JvMhck?si=RgZR6_GivuQWukcm"
        )
        self.assertEqual(
            candidates,
            ['bestvideo[ext=mp4][filesize<7M]+bestaudio[ext=m4a][filesize<1050K]/b[ext=mp4][filesize<8M]/best[filesize<8M]', 'best']
        )

    def test_get_format_candidates_for_youtube_watch_url(self):
        candidates = downloader_module._get_format_candidates(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        self.assertEqual(
            candidates,
            ['bestvideo[ext=mp4][filesize<7M]+bestaudio[ext=m4a][filesize<1050K]/b[ext=mp4][filesize<8M]/best[filesize<8M]', 'best']
        )

    def test_create_opts_sets_format_sort_for_filesize(self):
        opts = downloader_module._create_ydl_opts('best[filesize<8M]/worst')
        self.assertEqual(opts['format'], 'best[filesize<8M]/worst')
        self.assertIn('+filesize', opts['format_sort'])
        self.assertEqual(opts['merge_output_format'], 'mp4')

    def test_create_opts_sets_format_sort_for_youtube_merge_selector(self):
        opts = downloader_module._create_ydl_opts(
            'bestvideo[ext=mp4][filesize<7M]+bestaudio[ext=m4a][filesize<1050K]/b[ext=mp4][filesize<8M]/best[filesize<8M]'
        )
        self.assertEqual(
            opts['format'],
            'bestvideo[ext=mp4][filesize<7M]+bestaudio[ext=m4a][filesize<1050K]/b[ext=mp4][filesize<8M]/best[filesize<8M]'
        )
        self.assertEqual(opts['format_sort'], ['+codec:h264'])
        self.assertEqual(opts['merge_output_format'], 'mp4')

    def test_create_opts_sets_format_sort_for_reddit_merge(self):
        opts = downloader_module._create_ydl_opts('bv*+ba/b')
        self.assertEqual(opts['format'], 'bv*+ba/b')
        self.assertEqual(opts['format_sort'], ['+codec:h264'])


class TestTikTokPlaywrightFallback(unittest.TestCase):

    def test_rejects_webvtt_payload_signature(self):
        self.assertTrue(
            tiktok_fallback_module._looks_like_webvtt_payload(
                b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\ncaption text\n"
            )
        )
        self.assertFalse(
            tiktok_fallback_module._looks_like_webvtt_payload(
                b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2"
            )
        )

    def test_extracts_video_candidates_from_html_and_ignores_non_video_urls(self):
        html = r'''
        <script>
        {
          "caption": "https:\u002F\u002Fv16-webapp.tiktok.com\u002Fvideo\u002Ftos\u002Fabc\u002F?a=1&item_id=123&format=webvtt",
          "play": "https:\u002F\u002Fv16-webapp-prime.tiktok.com\u002Fvideo\u002Ftos\u002Fabc\u002F?a=1&item_id=123&mime_type=video_mp4",
          "avatar": "https:\u002F\u002Fp16-sign.tiktokcdn.com\u002Favatar.jpeg"
        }
        </script>
        '''
        self.assertEqual(
            tiktok_fallback_module._extract_tiktok_media_urls_from_html(html, "123"),
            [
                "https://v16-webapp.tiktok.com/video/tos/abc/?a=1&item_id=123&format=webvtt",
                "https://v16-webapp-prime.tiktok.com/video/tos/abc/?a=1&item_id=123&mime_type=video_mp4",
            ],
        )

    def test_rejects_vtt_media_response(self):
        self.assertFalse(
            tiktok_fallback_module._is_downloadable_tiktok_video_response(
                "https://v16-webapp-prime.tiktokcdn.com/abc/subtitles/en.vtt?item_id=123",
                "text/vtt",
                "media",
                "123",
            )
        )

    def test_accepts_mp4_media_response(self):
        self.assertTrue(
            tiktok_fallback_module._is_downloadable_tiktok_video_response(
                "https://v16-webapp-prime.tiktokcdn.com/video/tos/useast5/tos-useast5-pve-0068-tx/o8.mp4?item_id=123",
                "video/mp4",
                "media",
                "123",
            )
        )

    def test_rejects_caption_url_even_with_generic_binary_content_type(self):
        self.assertFalse(
            tiktok_fallback_module._is_downloadable_tiktok_video_response(
                "https://v16-webapp-prime.tiktokcdn.com/caption/file.vtt?item_id=123",
                "application/octet-stream",
                "fetch",
                "123",
            )
        )

if __name__ == '__main__':
    unittest.main()
