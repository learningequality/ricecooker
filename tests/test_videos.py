from __future__ import print_function
import os
import pytest
import re
import requests
import shutil
import subprocess
import tempfile

IS_TRAVIS_TESTING = "TRAVIS" in os.environ and os.environ["TRAVIS"] == "true"

from le_utils.constants import format_presets
from pressurecooker import videos

from ricecooker import config
from ricecooker.classes.files import VideoFile, FILECACHE

from cachecontrol.caches.file_cache import FileCache
from ricecooker.classes.files import FILECACHE


@pytest.fixture
def low_res_video():
    if os.path.exists("tests/testcontent/low_res_video.mp4"):
        f = open("tests/testcontent/low_res_video.mp4", 'rb')
        f.close()
    else:
        with open("tests/testcontent/low_res_video.mp4", 'wb') as f:
            resp = requests.get(
                "https://archive.org/download/vd_is_for_everybody/vd_is_for_everybody_512kb.mp4",
                stream=True,
            )
            for chunk in resp.iter_content(chunk_size=1048576):
                f.write(chunk)
            f.flush()
    return f  # returns a closed file descriptor which we use for name attribute


@pytest.fixture
def high_res_video():
    if not os.path.exists("tests/testcontent/high_res_video.mp4"):
        with open("tests/testcontent/high_res_video.mp4", 'wb') as f:
            resp = requests.get(
                "https://ia800201.us.archive.org/7/items/"
                "UnderConstructionFREEVideoBackgroundLoopHD1080p/"
                "UnderConstruction%20-%20FREE%20Video%20Background%20Loop%20HD%201080p.mp4",
                stream=True
            )
            for chunk in resp.iter_content(chunk_size=1048576):
                f.write(chunk)
            f.flush()
    else:
        f = open("tests/testcontent/high_res_video.mp4", 'rb')
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute


@pytest.fixture
def low_res_ogv_video():
    if not os.path.exists("tests/testcontent/low_res_ogv_video.ogv"):
        with open("tests/testcontent/low_res_ogv_video.ogv", 'wb') as f:
            resp = requests.get(
                "https://archive.org/download/"
                "UnderConstructionFREEVideoBackgroundLoopHD1080p/"
                "UnderConstruction%20-%20FREE%20Video%20Background%20Loop%20HD%201080p.ogv",
                stream=True
            )
            for chunk in resp.iter_content(chunk_size=1048576):
                f.write(chunk)
            f.flush()
    else:
        f = open("tests/testcontent/low_res_ogv_video.ogv", 'rb')
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute


@pytest.fixture
def bad_video():
    if not os.path.exists("tests/testcontent/bad_video.mp4"):
        with open("tests/testcontent/bad_video.mp4", 'wb') as f:
            f.write(b'novideohere. ffmpeg soshould error')
            f.flush()
    else:
        f = open("tests/testcontent/bad_video.mp4", 'rb')
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute




def make_video_file(video_file_file, language='en'):
    """
    Creates a VideoFile object with path taken from `video_file_file.name`.
    """
    return VideoFile(video_file_file.name, language=language)



""" *********** TEST BASIC VIDEO PROCESSING  *********** """


@pytest.mark.skipif(IS_TRAVIS_TESTING, reason="Skipping ffmpeg tests on Travis.")
class Test_video_processing_and_presets(object):

    def setup_method(self):
        _clear_ricecookerfilecache()

    def test_basic_video_processing_low_res(self, low_res_video):
        expected_video_filename = '897d83a2e5389d454d37feb574587516.mp4'
        video_file = make_video_file(low_res_video)
        video_filename = video_file.process_file()
        assert video_filename == expected_video_filename, "Video file should have filename {}".format(expected_video_filename)
        video_path = config.get_storage_path(video_filename)
        assert os.path.isfile(video_path), "Video should be stored at {}".format(video_path)
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'


    def test_basic_video_processing_high_res(self, high_res_video):
        expected_video_filename = 'e0ca22680786379362d0c95db2318853.mp4'
        video_file = make_video_file(high_res_video)
        video_filename = video_file.process_file()
        assert video_filename == expected_video_filename, "Video file should have filename {}".format(expected_video_filename)
        assert video_file.get_preset() == format_presets.VIDEO_HIGH_RES, 'Should have high res preset'





""" *********** TEST VIDEO COMPRESSION  *********** """


def get_resolution(videopath):
    """Helper function to get resolution of video at videopath."""
    result = subprocess.check_output(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_entries',
                                      'stream=width,height', '-of', 'default=noprint_wrappers=1', str(videopath)])
    pattern = re.compile('width=([0-9]*)[^height]+height=([0-9]*)')
    m = pattern.search(str(result))
    width, height = int(m.group(1)), int(m.group(2))
    return width, height

@pytest.mark.skipif(IS_TRAVIS_TESTING, reason="Skipping ffmpeg tests on Travis.")
class Test_video_compression(object):

    def setup_method(self):
        _clear_ricecookerfilecache()

    def test_default_compression_works(self, high_res_video):
        video_file = make_video_file(high_res_video)
        video_file.ffmpeg_settings = {'crf': 33}
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 480, 'should compress to 480 v resolution by defualt'
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'


    def test_compression_works(self, high_res_video):
        video_file = make_video_file(high_res_video)
        video_file.ffmpeg_settings = {'crf': 33, 'max_height': 300}
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 300, 'should be compress to 300 v resolution'
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'


    def test_compression_works(self, high_res_video):
        video_file = make_video_file(high_res_video)
        video_file.ffmpeg_settings = {'crf': 33, 'max_height': 300}
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 300, 'should be compress to 300 v resolution'
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'


    def test_handles_bad_file(self, bad_video):
        video_file = make_video_file(bad_video)
        video_file.ffmpeg_settings = {'crf': 33}
        video_filename = video_file.process_file()
        assert video_filename == None, 'Should return None if trying to compress bad file'
        assert "Invalid data" in str(video_file.error), 'File object should have error details'
        assert video_file in config.FAILED_FILES, 'Video file sould be added to config.FAILED_FILES'





""" *********** TEST VIDEO CONVERSION  *********** """

@pytest.mark.skipif(IS_TRAVIS_TESTING, reason="Skipping ffmpeg tests on Travis.")
class Test_video_conversion(object):

    def setup_method(self):
        _clear_ricecookerfilecache()

    def test_convert_ogv_works(self, low_res_ogv_video):
        video_file = make_video_file(low_res_ogv_video)
        video_file.ffmpeg_settings = {'crf': 33, 'max_height': 300}
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 300, 'should be compress to 300 v resolution'
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'

    def test_convert_and_resize_ogv_works(self, low_res_ogv_video):
        video_file = make_video_file(low_res_ogv_video)
        video_file.ffmpeg_settings = {'crf': 33, 'max_height': 200}
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 200, 'should be compress to 200 v resolution'
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'




""" HELPER METHODS """

def _clear_ricecookerfilecache():
    """
    Clear `.ricecookerfilecache` dir contents so each test runs in a clean env.
    """
    folder = config.FILECACHE_DIRECTORY
    for the_file in os.listdir(folder):
        file_path = os.path.join(folder, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(e)

