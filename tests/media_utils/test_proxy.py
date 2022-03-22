import os

import pytest

from ricecooker.utils import proxy
from ricecooker.utils.youtube import YouTubeResource


YOUTUBE_TEST_VIDEO = "https://www.youtube.com/watch?v=C0DPdy98e4c"
YOUTUBE_TEST_PLAYLIST = "https://www.youtube.com/playlist?list=PL472BC6F4F2C3ABEF"


# This test takes a few minutes, but is very useful for checking that the proxy is not being ignored,
# so mark it to run when the PYTEST_RUN_SLOW env var is set.
@pytest.mark.skipif(
    "PYTEST_RUN_SLOW" not in os.environ,
    reason="This test takes several minutes to complete.",
)
def test_bad_proxies_get_banned(tmp_path):
    # create some fake proxies...
    FAKE_PROXIES = [
        "122.123.123.123:1234",
        "142.123.1.234:123345",
        "156.245.233.211:12323",
        "11.22.33.44:123",
    ]
    # initialize PROXY_LIST to known-bad proxies to check that they get banned
    proxy.PROXY_LIST = FAKE_PROXIES.copy()

    video = YouTubeResource(YOUTUBE_TEST_VIDEO)
    video.download(tmp_path)

    # Fake proxies should get added to BROKEN_PROXIES
    assert set(FAKE_PROXIES).issubset(set(proxy.BROKEN_PROXIES))


@pytest.mark.skipif(
    "PYTEST_RUN_SLOW" not in os.environ,
    reason="This test can take several minutes to complete.",
)
def test_proxy_download(tmp_path):
    proxy.get_proxies(refresh=True)
    assert len(proxy.PROXY_LIST) > 1

    video = YouTubeResource(YOUTUBE_TEST_VIDEO)
    video.download(tmp_path)

    temp_files = os.listdir(os.path.join(tmp_path, "Watch"))
    has_video = False
    for afile in temp_files:
        if afile.endswith(".mp4"):
            has_video = True

    assert has_video, "Video file not found"


@pytest.mark.skipif(
    "PYTEST_RUN_SLOW" not in os.environ,
    reason="This test can take several minutes to complete.",
)
def test_proxy_playlist_download(tmp_path):
    playlist = YouTubeResource(YOUTUBE_TEST_PLAYLIST)
    playlist.download(tmp_path)

    temp_files = os.listdir(os.path.join(tmp_path, "Playlist"))
    expected = [
        "zbkizy-Y3qw.jpg",
        "oXnzstpBEOg.mp4",
        "oXnzstpBEOg.jpg",
        "zbkizy-Y3qw.mp4",
    ]

    assert set(temp_files) == set(expected)
