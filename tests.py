import unittest
from validator import extractUrl, isSupportedUrl
from downloader import download
from dbInteraction import savePost, doesPostExist
from calculator import calculateBitrate, calculateBitrateAudioOnly

class TestUrlParser(unittest.TestCase):

    def test_supportedUrl(self):
        url = "https://vt.tiktok.com/ZSrSTRC29/"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'true')

    def test_unsupportedUrl(self):
        url = "https://www.twitch.tv/robcdee/clip/AgileLivelyCucumberPartyTime"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'false')

class TestDownloader(unittest.TestCase):

    def test_imgur_gallery(self):
        url = "https://imgur.com/gallery/1jK60ka/"
        downloadResponse = download(url, detect_repost=False)
        self.assertEqual(downloadResponse["messages"], '')
    
    def test_tiktok(self):
        url = "https://vt.tiktok.com/ZSrSTRC29/"
        downloadResponse = download(url, detect_repost=False)
        self.assertEqual(downloadResponse["messages"], '')

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

if __name__ == '__main__':
    unittest.main()