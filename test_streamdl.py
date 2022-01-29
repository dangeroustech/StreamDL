import os
import unittest
from streamdl import config_reader
from streamdl import yt_download


class TestConfigReader(unittest.TestCase):
    def test_empty(self):
        """
        Test that the config reader returns a real object
        """
        data_loaded = config_reader("config.yml.example")
        self.assertIsNotNone(data_loaded)

    def test_object_type(self):
        """
        Test that the config reader returns the correct object type
        """
        data_loaded = config_reader("config.yml.example")
        self.assertIs(type(data_loaded), dict)

    def test_full_yaml(self):
        """
        Test that the config reader returns the correct YAML
        """
        data_loaded = config_reader("config.yml.example")
        example_yaml = {"twitch.tv": ["kaypealol", "day9tv"], "mixer.com": ["ninja"]}
        self.assertEqual(data_loaded, example_yaml)


class TestDownloadVideo(unittest.TestCase):
    def test_valid_url(self):
        """
        Test that a good URL succeeds by downloading nyan cat
        """
        url = "youtube.com"
        user = "watch?v=v2GCfSGFkG0"
        self.assertTrue(yt_download(url, user, os.getcwd() + "/media/"))

    def test_offline_twitch(self):
        """
        Test that a good URL succeeds by downloading nyan cat
        """
        url = "twitch.tv"
        user = "biodrone"
        self.assertTrue(yt_download(url, user, os.getcwd() + "/media/"))

    def test_invalid_url(self):
        """
        Test that a bad URL fails because example.com doesn't have nyan cat :(
        """
        url = "example.com"
        user = "watch?v=QH2-TGUlwu4"
        self.assertFalse(yt_download(url, user, os.getcwd() + "/media/"))

    def test_non_video_url(self):
        """
        Test that a non video site exits quietly
        """
        url = "dangerous.tech"
        user = "watch?v=QH2-TGUlwu4"
        self.assertTrue(yt_download(url, user, os.getcwd() + "/media/"))


if __name__ == "__main__":
    unittest.main()
