import os
import pytest

from ricecooker.utils.youtube_cache import * 



""" *********** YouTube Cache FIXTURES *********** """

@pytest.fixture
def youtube_video_cache():
    cache_dir = os.path.join('tests', 'testcontent', 'youtubecache')
    assert os.path.isdir(cache_dir), 'Incorrect directory path setting'
    return YouTubeVideoCache(video_id='DFZb2qBIrEw', alias='test-video', cache_dir=cache_dir)



""" *********** YouTube Cache TESTS *********** """

def test_youtube_video_cache(youtube_video_cache):
    youtube_video_cache.get_video_info()
    video_cache_filepath = os.path.join('tests', 'testcontent', 'youtubecache', 'test-video.json')
    assert os.path.exists(video_cache_filepath)
