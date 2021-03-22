from __future__ import print_function
from cachecontrol.caches.file_cache import FileCache
import os
import pytest
import re
import shutil
import subprocess

from le_utils.constants import format_presets
from le_utils.constants import licenses
from pressurecooker import videos
from ricecooker import config
from ricecooker.classes.files import FILECACHE
from ricecooker.classes.files import SubtitleFile, VideoFile, YouTubeVideoFile
from ricecooker.classes.nodes import VideoNode

from conftest import download_fixture_file


@pytest.fixture
def low_res_video():
    source_url = "https://archive.org/download/vd_is_for_everybody/vd_is_for_everybody_512kb.mp4"
    local_path = os.path.join("tests", "testcontent", "downloaded", "low_res_video.mp4")
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    f = open(local_path, 'rb')
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute

@pytest.fixture
def low_res_video_webm():
    source_url = "https://ia801800.us.archive.org/28/items/rick-astley-never-gonna-give-you-up-video_202012/" \
                 "Rick%20Astley%20-%20Never%20Gonna%20Give%20You%20Up%20Video.webm"
    local_path = os.path.join("tests", "testcontent", "downloaded", "low_res_video.webm")
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    f = open(local_path, 'rb')
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute

@pytest.fixture
def high_res_video():
    source_url = "https://ia800201.us.archive.org/7/items/" \
                 "UnderConstructionFREEVideoBackgroundLoopHD1080p/" \
                 "UnderConstruction%20-%20FREE%20Video%20Background%20Loop%20HD%201080p.mp4"
    local_path = os.path.join("tests", "testcontent", "downloaded", "high_res_video.mp4")
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    f = open(local_path, 'rb')
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute

@pytest.fixture
def high_res_video_webm():
    source_url = "https://mirrors.creativecommons.org/movingimages/webm/CreativeCommonsPlusCommercial_720p.webm"
    local_path = os.path.join("tests", "testcontent", "downloaded", "high_res_video.webm")
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    f = open(local_path, 'rb')
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute

@pytest.fixture
def low_res_ogv_video():
    source_url = "https://archive.org/download/" \
                 "UnderConstructionFREEVideoBackgroundLoopHD1080p/" \
                 "UnderConstruction%20-%20FREE%20Video%20Background%20Loop%20HD%201080p.ogv"
    local_path = os.path.join("tests", "testcontent", "downloaded", "low_res_ogv_video.ogv")
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    f = open(local_path, 'rb')
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute

@pytest.fixture
def bad_video():
    local_path = os.path.join("tests", "testcontent", "generated", "bad_video.mp4")
    if not os.path.exists(local_path):
        with open(local_path, 'wb') as f:
            f.write(b'novideohere. so ffmpeg should error out!')
            f.flush()
    else:
        f = open(local_path, 'rb')
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute


def make_video_file(video_file_file, language='en'):
    """
    Creates a VideoFile object with path taken from `video_file_file.name`.
    """
    return VideoFile(video_file_file.name, language=language)


""" *********** TEST BASIC VIDEO PROCESSING  *********** """


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

    def test_basic_video_processing_low_res_webm(self, low_res_video_webm):
        expected_video_filename = '5a2172860b2de19d746d00e3deeae3a7.webm'
        video_file = make_video_file(low_res_video_webm)
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

    def test_basic_video_processing_high_res_webm(self, high_res_video_webm):
        expected_video_filename = '06b4e0d8c50f2224868086ad2fb92511.webm'
        video_file = make_video_file(high_res_video_webm)
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


    def test_compression_max_width_works(self, high_res_video):
        video_file = make_video_file(high_res_video)
        video_file.ffmpeg_settings = {'crf': 33, 'max_width': 200}
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert width == 200, 'should be compress to 200 hz resolution'
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, 'Should have low res preset'


    def test_handles_bad_file(self, bad_video):
        video_file = make_video_file(bad_video)
        video_file.ffmpeg_settings = {'crf': 33}
        video_filename = video_file.process_file()
        assert video_filename == None, 'Should return None if trying to compress bad file'
        assert "Invalid data" in str(video_file.error), 'File object should have error details'
        assert video_file in config.FAILED_FILES, 'Video file sould be added to config.FAILED_FILES'





""" *********** TEST VIDEO CONVERSION  *********** """
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
    if os.path.exists(folder):
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(e)



""" *********** TEST SUBTITLES CONVERSION  *********** """
# see section SUBTITLEFILE TESTS in test_files.py



""" *********** TEST VIDEO FILE SUBS VALIDATION  *********** """

def test_multiple_subs_can_be_added(video_file):
    """
    Baseline check to make sure we're not dropping subtitle files on validate.
    """
    local_path = os.path.join("tests", "testcontent", "samples", "testsubtitles_ar.srt")
    assert os.path.exists(local_path)
    video_node = VideoNode('vid-src-id', "Video", licenses.PUBLIC_DOMAIN)
    video_node.add_file(video_file)
    sub1 = SubtitleFile(local_path, language='en')
    video_node.add_file(sub1)
    sub2 = SubtitleFile(local_path, language='ar')
    video_node.add_file(sub2)
    video_node.validate()
    sub_files = [f for f in video_node.files if isinstance(f, SubtitleFile)]
    assert len(sub_files) == 2, 'Missing subtitles files!'

def test_duplicate_language_codes_fixed_by_validate(video_file):
    """
    Video nodes should have at most one subtitle file for a particular lang code.
    """
    local_path = os.path.join("tests", "testcontent", "samples", "testsubtitles_ar.srt")
    assert os.path.exists(local_path)
    video_node = VideoNode('vid-src-id', "Video", licenses.PUBLIC_DOMAIN)
    video_node.add_file(video_file)
    sub1 = SubtitleFile(local_path, language='ar')
    video_node.add_file(sub1)
    # now let's add file with a duplicate language code...
    sub2 = SubtitleFile(local_path, language='ar')
    video_node.add_file(sub2)
    video_node.validate()
    sub_files = [f for f in video_node.files if isinstance(f, SubtitleFile)]
    assert len(sub_files) == 1, 'Duplicate subtitles files not removed!'
