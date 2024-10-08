import os
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from ricecooker.utils.youtube import YouTubePlaylistUtils
from ricecooker.utils.youtube import YouTubeVideoUtils

""" *********** YouTube Cache FIXTURES *********** """


@pytest.fixture
def youtube_video_cache():
    cache_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "testcontent", "youtubecache")
    )
    assert os.path.isdir(cache_dir), "Incorrect directory path setting"
    return YouTubeVideoUtils(id="zzJLYK893gQ", alias="test-video", cache_dir=cache_dir)


@pytest.fixture
def youtube_playlist_cache():
    cache_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "testcontent", "youtubecache")
    )
    assert os.path.isdir(cache_dir), "Incorrect directory path setting"
    return YouTubePlaylistUtils(
        id="PLOZioxrIwCv33zt5aFFjWqDoEMm55MVA9",
        alias="test-playlist",
        cache_dir=cache_dir,
    )


""" *********** YouTube Cache TESTS *********** """


def test_youtube_video_cache(youtube_video_cache):
    mock_video_info = {
        "artist": "JLRR",
        "description": "Jamie Alexandre, Learning Equality's co-founder shares ....",
        "ext": "mp4",
        "id": "zzJLYK893gQ",
        "kind": "video",
        "license": "Creative Commons Attribution license (reuse allowed)",
        "requested_subtitles": None,
        "source_url": "https://www.youtube.com/watch?v=zzJLYK893gQ",
        "subtitles": {},
        "tags": [],
        "thumbnail": "https://i.ytimg.com/vi/zzJLYK893gQ/maxresdefault.jpg",
        "title": "Learning Equality's Pledge to UNESCO's Global Education Coalition",
    }

    with patch("ricecooker.utils.youtube.yt_dlp.YoutubeDL") as mock_youtube_dl_class:
        mock_youtube_dl_instance = MagicMock()
        mock_youtube_dl_class.return_value = mock_youtube_dl_instance
        mock_youtube_dl_instance.extract_info.return_value = mock_video_info

        video_info = youtube_video_cache.get_video_info(
            use_proxy=False, get_subtitle_languages=True
        )
    video_cache_filepath = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "youtubecache", "test-video.json"
        )
    )
    assert video_info and os.path.exists(video_cache_filepath)


def test_youtube_playlist_cache(youtube_playlist_cache):
    playlist_info = youtube_playlist_cache.get_playlist_info(use_proxy=False)
    playlist_cache_filepath = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "youtubecache",
            "test-playlist.json",
        )
    )
    assert playlist_info and os.path.exists(playlist_cache_filepath)
