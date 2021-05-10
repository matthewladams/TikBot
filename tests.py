import unittest
from validator import extractUrl, isSupportedUrl
from downloader import download

class TestUrlParser(unittest.TestCase):

    def test_supportedUrl(self):
        url = "https://vm.tiktok.com/ZSJrgyXdt/"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'true')

    def test_unsupportedUrl(self):
        url = "https://www.twitch.tv/robcdee/clip/AgileLivelyCucumberPartyTime"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'false')

class TestDownloader(unittest.TestCase):

    def test_imgur_gallery(self):
        url = "https://imgur.com/gallery/1jK60ka/"
        downloadResponse = download(url)
        self.assertEqual(downloadResponse["messages"], '')

if __name__ == '__main__':
    unittest.main()