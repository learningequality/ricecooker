import os
import shutil
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from le_utils.constants import file_formats

from ricecooker.utils import utils
from ricecooker.utils import youtube

trees = {}
yt_resources = {}
USE_PROXY_FOR_TESTS = False

cc_playlist = "https://www.youtube.com/playlist?list=PL7m903CwFUgntbjkVMwts89fZq0INCtVS"
non_cc_playlist = (
    "https://www.youtube.com/playlist?list=PLBO8M-O_dTPE51ymDUgilf8DclGAEg9_A"
)
subtitles_video = "https://www.youtube.com/watch?v=6uXAbJQoZlE"
subtitles_zu_video = "https://www.youtube.com/watch?v=FN12ty5ztAs"

mock_extract_info_non_cc_return_value = {
    "id": "test_playlist_id",
    "kind": "playlist",
    "title": "Test Playlist",
    "entries": [
        {"id": "video1", "kind": "video", "title": "Test Video 1"},
        {"id": "video2", "kind": "video", "title": "Test Video 2"},
        {"id": "video3", "kind": "video", "title": "Test Video 3"},
        {"id": "video4", "kind": "video", "title": "Test Video 4"},
    ],
}

mock_extract_info_cc_return_value = {
    "id": "test_playlist_id",
    "kind": "playlist",
    "title": "Test Playlist",
    "entries": [
        {
            "id": "video1",
            "kind": "video",
            "title": "Test Video 1",
            "license": "Creative Commons Attribution license (reuse allowed)",
        },
        {
            "id": "video2",
            "kind": "video",
            "title": "Test Video 2",
            "license": "Creative Commons Attribution license (reuse allowed)",
        },
        {
            "id": "video3",
            "kind": "video",
            "title": "Test Video 3",
            "license": "Creative Commons Attribution license (reuse allowed)",
        },
        {"id": "video4", "kind": "video", "title": "Test Video 4", "license": ""},
    ],
}

mock_extract_info_subtitles_return_value = {
    "id": "6uXAbJQoZlE",
    "title": "Investing in Education Instead of Speculation",
    "description": "Unlike speculation in crypto-currencies....",
    "ext": "mp4",
    "source_url": "https://www.youtube.com/watch?v=6uXAbJQoZlE",
    "subtitles": {
        "zh-CN": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=zh-CN&fmt=vtt",
                "name": "Chinese (China)",
            },
        ],
        "en": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=en&fmt=vtt",
                "name": "English",
            },
        ],
        "ru": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=ru&fmt=vtt",
                "name": "Russian",
            },
        ],
        "es": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=es&fmt=vtt",
                "name": "Spanish",
            },
        ],
    },
    "artist": "",
    "license": "Creative Commons Attribution license (reuse allowed)",
    "kind": "video",
}

mock_extract_info_subtitles_zu_return_value = {
    "id": "FN12ty5ztAs",
    "title": "Amanda and friends play cans game in South Africa",
    "description": "Bla bla bla.",
    "ext": "mp4",
    "source_url": "https://www.youtube.com/watch?v=FN12ty5ztAs",
    "tags": ["yt:cc=on"],
    "subtitles": {
        "en-5IebwaT_cAk": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=en&name=+via+Dotsub&fmt=vtt",
                "name": "English -  via Dotsub",
            },
        ],
        "fr-5IebwaT_cAk": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=fr&name=+via+Dotsub&fmt=vtt",
                "name": "French -  via Dotsub",
            },
        ],
        "zu-5IebwaT_cAk": [
            {
                "ext": "vtt",
                "url": "https://www.youtube.com/api/whatever&key=yt8&lang=zu&name=+via+Dotsub&fmt=vtt",
                "name": "Zulu -  via Dotsub",
            },
        ],
    },
    "requested_subtitles": {
        "zu-5IebwaT_cAk": {
            "ext": "vtt",
            "url": "https://www.youtube.com/api/whatever&key=yt8&lang=zu&name=+via+Dotsub&fmt=vtt",
            "name": "Zulu -  via Dotsub",
        },
    },
    "artist": "",
    "license": "",
    "kind": "video",
}


def get_yt_resource(url, **kwargs):
    global yt_resources
    if url not in yt_resources:
        if "useproxy" not in kwargs:
            if USE_PROXY_FOR_TESTS:
                kwargs["useproxy"] = True
            else:
                kwargs["useproxy"] = False
        yt_resources[url] = youtube.YouTubeResource(url, **kwargs)

    return yt_resources[url]


def test_get_youtube_info():
    with patch("ricecooker.utils.youtube.yt_dlp.YoutubeDL") as mock_youtube_dl_class:
        mock_youtube_dl_instance = MagicMock()
        mock_youtube_dl_class.return_value = mock_youtube_dl_instance
        mock_youtube_dl_instance.extract_info.return_value = (
            mock_extract_info_non_cc_return_value
        )

        yt_resource = get_yt_resource(non_cc_playlist)
        tree = yt_resource.get_resource_info()
    assert tree["id"]
    assert tree["kind"]
    assert tree["title"]
    assert len(tree["children"]) == 4

    for video in tree["children"]:
        assert video["id"]
        assert video["kind"]
        assert video["title"]


def test_warnings_no_license():
    with patch("ricecooker.utils.youtube.yt_dlp.YoutubeDL") as mock_youtube_dl_class:
        mock_youtube_dl_instance = MagicMock()
        mock_youtube_dl_class.return_value = mock_youtube_dl_instance
        mock_youtube_dl_instance.extract_info.return_value = (
            mock_extract_info_non_cc_return_value
        )

        yt_resource = get_yt_resource(non_cc_playlist)
        issues, output_info = yt_resource.check_for_content_issues()

    assert len(issues) == 4
    for issue in issues:
        assert "no_license_specified" in issue["warnings"]


def test_cc_no_warnings():
    with patch("ricecooker.utils.youtube.yt_dlp.YoutubeDL") as mock_youtube_dl_class:
        mock_youtube_dl_instance = MagicMock()
        mock_youtube_dl_class.return_value = mock_youtube_dl_instance
        mock_youtube_dl_instance.extract_info.return_value = (
            mock_extract_info_cc_return_value
        )

        yt_resource = get_yt_resource(cc_playlist)
        issues, output_info = yt_resource.check_for_content_issues()

    # there is one video in this playlist that is not cc-licensed
    assert len(issues) == 1
    for issue in issues:
        assert "no_license_specified" in issue["warnings"]


@pytest.mark.skipif(True, reason="Skipping download tests.")
def test_download_youtube_video():
    download_dir = tempfile.mkdtemp()

    try:
        yt_resource = get_yt_resource(subtitles_video)
        info = yt_resource.download(base_path=download_dir)
        assert info
        if info:
            assert "filename" in info
            assert os.path.exists(
                info["filename"]
            ), "Filename {} does not exist".format(info["filename"])

    finally:
        shutil.rmtree(download_dir)


@pytest.mark.skipif(True, reason="Skipping download tests.")
def test_download_youtube_playlist():
    download_dir = tempfile.mkdtemp()

    try:
        yt_resource = get_yt_resource(cc_playlist)
        info = yt_resource.download(base_path=download_dir)
        assert info is not None
        if info:
            assert "filename" not in info
            assert "children" in info
            for child in info["children"]:
                assert "filename" in child
                assert os.path.exists(
                    child["filename"]
                ), "Filename {} does not exist".format(child["filename"])

    finally:
        shutil.rmtree(download_dir)


def test_get_subtitles():
    with patch("ricecooker.utils.youtube.yt_dlp.YoutubeDL") as mock_youtube_dl_class:
        mock_youtube_dl_instance = MagicMock()
        mock_youtube_dl_class.return_value = mock_youtube_dl_instance
        mock_youtube_dl_instance.extract_info.return_value = (
            mock_extract_info_subtitles_return_value
        )

        yt_resource = get_yt_resource(subtitles_video)
        info = yt_resource.get_resource_subtitles()
    assert len(info["subtitles"]) == 4  # brittle; can change if subs get added
    assert "ru" in info["subtitles"]
    assert "en" in info["subtitles"]
    assert "zh-CN" in info["subtitles"]
    assert "es" in info["subtitles"]


def test_non_youtube_url_error():
    url = "https://vimeo.com/238190750"
    with pytest.raises(utils.VideoURLFormatError):
        youtube.YouTubeResource(url)


def test_subtitles_lang_helpers_compatible():
    """
    Usage examples functions `is_youtube_subtitle_file_supported_language` and
    `_get_language_with_alpha2_fallback` that deal with language codes.
    """
    with patch("ricecooker.utils.youtube.yt_dlp.YoutubeDL") as mock_youtube_dl_class:
        mock_youtube_dl_instance = MagicMock()
        mock_youtube_dl_class.return_value = mock_youtube_dl_instance
        mock_youtube_dl_instance.extract_info.return_value = (
            mock_extract_info_subtitles_zu_return_value
        )
        yt_resource = get_yt_resource(subtitles_zu_video)
        info = yt_resource.get_resource_subtitles()
    all_subtitles = info["subtitles"]

    # 1. filter out non-vtt subs
    vtt_subtitles = {}
    for youtube_language, subs in all_subtitles.items():
        vtt_subtitles[youtube_language] = [s for s in subs if s["ext"] == "vtt"]

    for youtube_language, sub_dict in vtt_subtitles.items():
        # 2. check compatibility with le-utils language codes (a.k.a. internal representation)
        verdict = youtube.is_youtube_subtitle_file_supported_language(youtube_language)
        assert (
            verdict
        ), f"Wrongly marked youtube_language {youtube_language} as incompatible"
        # 3. TODO: figure out what to do for incompatible langs

        # 4. map youtube_language to le-utils language code (a.k.a. internal representation)
        language_obj = youtube.get_language_with_alpha2_fallback(youtube_language)
        assert (
            language_obj is not None
        ), "Failed to find matchin language code in le-utils"
        if youtube_language == "zu":
            assert (
                language_obj.code == "zul"
            ), "Matched to wrong language code in le-utils"


def test_subtitles_lang_helpers_incompatible():
    """
    Ensure `is_youtube_subtitle_file_supported_language` rejects unknown language codes.
    """
    verdict1 = youtube.is_youtube_subtitle_file_supported_language("patapata")
    assert verdict1 is False, "Failed to reject incompatible youtube_language"
    verdict2 = youtube.is_youtube_subtitle_file_supported_language("zzz")
    assert verdict2 is False, "Failed to reject incompatible youtube_language"


@pytest.mark.skipif(
    "PYTEST_RUN_SLOW" not in os.environ,
    reason="This test can take several minutes to complete.",
)
@pytest.mark.parametrize("useproxy", [True, False])
@pytest.mark.parametrize("useproxy_for_download", [False])
def test_download_from_web_video_file(tmp_path, useproxy, useproxy_for_download):
    """
    Test for functionality required by download_from_web for WebVideoFile processing.
    """
    for youtube_url in [subtitles_video, subtitles_zu_video]:
        download_ext = ".{ext}".format(ext=file_formats.MP4)
        destination_path = os.path.join(tmp_path, youtube_url[-11:] + download_ext)

        # STEP 1: get_resource_info via proxy
        settings = {}
        maxheight = 480
        settings[
            "format"
        ] = "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(
            maxheight=maxheight
        )
        settings["outtmpl"] = destination_path
        yt_resource = youtube.YouTubeResource(
            youtube_url, useproxy=useproxy, options=settings
        )
        video_node1 = yt_resource.get_resource_info()
        assert video_node1, "no data returned"

        # STEP 2: download
        # overwrite default download behaviour by setting custom options
        download_settings = {}
        download_settings["writethumbnail"] = False
        download_settings["outtmpl"] = destination_path
        _ = yt_resource.download(
            options=download_settings, useproxy=useproxy_for_download
        )
        assert os.path.exists(destination_path), "Missing video file"


@pytest.mark.skipif(
    "PYTEST_RUN_SLOW" not in os.environ,
    reason="This test can take several minutes to complete.",
)
@pytest.mark.parametrize("useproxy", [True, False])
@pytest.mark.parametrize("useproxy_for_download", [False])
def test_download_from_web_subtitle_file(tmp_path, useproxy, useproxy_for_download):
    """
    Use YouTubeResource the same way YouTubeSubtitleFile when proxy is enabled.
    """
    for youtube_url, lang in [(subtitles_video, "ru"), (subtitles_zu_video, "zu")]:
        destination_path_noext = os.path.join(tmp_path, youtube_url[-11:])
        download_ext = ".{lang}.{ext}".format(lang=lang, ext=file_formats.VTT)
        destination_path = destination_path_noext + download_ext

        # STEP 1: get_resource_info
        settings = {
            "outtmpl": destination_path_noext,  # note no ext -- YoutubeDL will auto append it,
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "best[ext={}]".format(file_formats.VTT),
            "quiet": True,
            "verbose": True,
            "no_warnings": True,
        }
        web_url = youtube_url
        yt_resource = youtube.YouTubeResource(
            web_url, useproxy=useproxy, options=settings
        )
        video_node = yt_resource.get_resource_info()
        # checks for STEP 1
        assert video_node["subtitles"], "missing subtitles key"

        # STEP 2: download
        # overwrite default download behaviour by setting custom options
        download_settings = {}
        download_settings["writethumbnail"] = False
        download_settings["outtmpl"] = destination_path_noext
        yt_resource.download(options=download_settings, useproxy=useproxy_for_download)
        # checks for STEP 2
        assert os.path.exists(destination_path), "Missing subtitles file"
