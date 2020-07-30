import os
import pytest

from ricecooker.utils.youtube import YouTubeVideoUtils, YouTubePlaylistUtils


""" *********** YouTube Cache FIXTURES *********** """

@pytest.fixture
def youtube_video_cache():
    cache_dir = os.path.join('tests', 'testcontent', 'youtubecache')
    assert os.path.isdir(cache_dir), 'Incorrect directory path setting'
    return YouTubeVideoUtils(id='zzJLYK893gQ', alias='test-video', cache_dir=cache_dir)

@pytest.fixture
def youtube_playlist_cache():
    cache_dir = os.path.join('tests', 'testcontent', 'youtubecache')
    assert os.path.isdir(cache_dir), 'Incorrect directory path setting'
    return YouTubePlaylistUtils(id='PLOZioxrIwCv33zt5aFFjWqDoEMm55MVA9', alias='test-playlist', cache_dir=cache_dir)


""" *********** YouTube Cache TESTS *********** """

def test_youtube_video_cache(youtube_video_cache):
    video_info = youtube_video_cache.get_video_info(use_proxy=False, get_subtitle_languages=True)
    video_cache_filepath = os.path.join('tests', 'testcontent', 'youtubecache', 'test-video.json')
    assert video_info and os.path.exists(video_cache_filepath)

def test_youtube_playlist_cache(youtube_playlist_cache):
    playlist_info = youtube_playlist_cache.get_playlist_info(use_proxy=False)
    playlist_cache_filepath = os.path.join('tests', 'testcontent', 'youtubecache', 'test-playlist.json')
    assert playlist_info and os.path.exists(playlist_cache_filepath)
    