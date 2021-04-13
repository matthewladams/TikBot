import unittest
from validator import extractUrl, isSupportedUrl

class TestUrlParser(unittest.TestCase):

    def test_supportedUrl(self):
        url = "https://vm.tiktok.com/ZSJrgyXdt/"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'true')

    def test_unsupportedUrl(self):
        url = "https://www.twitch.tv/robcdee/clip/AgileLivelyCucumberPartyTime"
        supportedResponse = isSupportedUrl(url)
        self.assertEqual(supportedResponse["supported"], 'false')

if __name__ == '__main__':
    unittest.main()