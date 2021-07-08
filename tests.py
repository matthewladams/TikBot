import unittest
from validator import extractUrl, isSupportedUrl
from downloader import download
from dbInteraction import savePost, doesPostExist

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

    # def test_imgur_gallery(self):
    #     url = "https://imgur.com/gallery/1jK60ka/"
    #     downloadResponse = download(url)
    #     self.assertEqual(downloadResponse["messages"], '')
    
    def test_tiktok(self):
        url = "https://vm.tiktok.com/ZSJbnjPMY/"
        downloadResponse = download(url)
        self.assertEqual(downloadResponse["messages"], '')

# TODO - how to safely test on github?
# class TestInsertDb(unittest.TestCase):

#     def test_insert_post(self):
#         savePost("Unit Test", "123420", "Fake Platform")

#     def test_post_exist(self):
#         doesPostExist("123420", "Fake Platform")

if __name__ == '__main__':
    unittest.main()