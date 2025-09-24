import contextlib
import os
import tempfile
import unittest
from unittest import mock

import downloader as downloader_module
from downloader import download
from calculator import calculateBitrate, calculateBitrateAudioOnly
from validator import isSupportedUrl


@contextlib.contextmanager
def temporary_working_directory():
    current = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        try:
            yield tmpdir
        finally:
            os.chdir(current)

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


@unittest.skipIf(IS_GITHUB_ACTIONS, "Reddit integration tests are blocked on GitHub Actions")
class TestDownloaderIntegration(DownloaderTestCase):

    REDDIT_URL = "https://www.reddit.com/r/justgalsbeingchicks/s/N7XkNUO9m4"

    def test_reddit_download_records_formats_and_saves_file(self):
        with temporary_working_directory() as tmpdir:
            download_response = download(self.REDDIT_URL, detect_repost=False)
            file_path = os.path.join(tmpdir, download_response["fileName"])

            if download_response["messages"]:
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

            self.assertTrue(os.path.exists(file_path))
            self.assertGreater(os.path.getsize(file_path), 0)
            self.assertGreater(download_response["duration"], 0)
            self.assertGreaterEqual(len(download_response["attemptedFormats"]), 1)
            self.assertIsNotNone(download_response["selectedFormat"])
            self.assertIn(download_response["selectedFormat"], download_response["attemptedFormats"])

        self.mock_does_post_exist.assert_not_called()

    def test_failed_download_reports_attempts(self):
        # Intentionally invalid video to trigger all fallbacks.
        url = "https://www.reddit.com/r/this_sub_does_not_exist/comments/abcdef/"

        with temporary_working_directory():
            download_response = download(url, detect_repost=False)

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

    def test_calculateBitrate_duration_limited(self):
        """Test calculateBitrate when duration is too long for quality"""
        duration = 10000  # Very long duration
        result = calculateBitrate(duration)
        self.assertEqual(result.videoBitrate, 300)  # Minimum video bitrate
        self.assertGreaterEqual(result.audioBitrate, 64)  # Minimum audio bitrate
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

    def test_create_opts_sets_format_sort_for_filesize(self):
        opts = downloader_module._create_ydl_opts('best[filesize<8M]/worst')
        self.assertEqual(opts['format'], 'best[filesize<8M]/worst')
        self.assertIn('+filesize', opts['format_sort'])
        self.assertEqual(opts['merge_output_format'], 'mp4')

    def test_create_opts_sets_format_sort_for_reddit_merge(self):
        opts = downloader_module._create_ydl_opts('bv*+ba/b')
        self.assertEqual(opts['format'], 'bv*+ba/b')
        self.assertEqual(opts['format_sort'], ['+codec:h264'])

if __name__ == '__main__':
    unittest.main()
