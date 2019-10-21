import os
import unittest
from streamdl import config_reader
from streamdl import download_video


class TestConfigReader(unittest.TestCase):
    def test_empty(self):
        """
        Test that the config reader returns a real object
        """
        data_loaded = config_reader('config.yml.example')
        self.assertIsNotNone(data_loaded)

    def test_yaml(self):
        """
        Test that the config reader returns the correct YAML
        """
        data_loaded = config_reader('config.yml.example')
        example_yaml = {'twitch.tv': ['kaypealol', 'day9tv'], 'youtube': ['UC4w1YQAJMWOz4qtxinq55LQ']}
        self.assertEqual(data_loaded, example_yaml)


class TestDownloadVideo(unittest.TestCase):
    def test_valid_url(self):
        """
        Test that a good URL succeeds by downloading nyan cat
        """
        url = 'www.youtube.com'
        user = 'watch?v=QH2-TGUlwu4'
        self.assertTrue(download_video(url, user, os.getcwd() + "/media/"))

    def test_invalid_url(self):
        """
        Test that a bad URL fails because test.com doesn't have nyan cat :(
        """
        url = 'example.com'
        user = 'watch?v=QH2-TGUlwu4'
        self.assertFalse(download_video(url, user, os.getcwd() + "/media/"))

    def test_moved_url(self):
        """
        Test that a 301 moved URL succeeds
        """
        url = 'youtube.com'
        user = 'watch?v=QH2-TGUlwu4'
        self.assertTrue(download_video(url, user, os.getcwd() + "/media/"))

    def test_non_video_url(self):
        """
        Test that a non video site exits quietly
        """
        url = 'test.com'
        user = 'watch?v=QH2-TGUlwu4'
        assert type == bytes
        self.assertTrue(download_video(url, user, os.getcwd() + "/media/"))


if __name__ == '__main__':
    unittest.main()
