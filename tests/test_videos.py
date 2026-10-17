from __future__ import print_function

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import sample_hash_filename
from conftest import sample_path
from le_utils.constants import format_presets
from le_utils.constants import licenses

from ricecooker import config
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import AudioFile
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.managers.tree import ChannelManager


def _closed_sample(*parts):
    """Open and close a committed sample so tests can use its ``.name`` attribute."""
    f = open(sample_path(*parts), "rb")
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute


@pytest.fixture
def low_res_video():
    return _closed_sample("low_res_sample.mp4")


@pytest.fixture
def low_res_video_webm():
    return _closed_sample("low_res_sample.webm")


@pytest.fixture
def high_res_video():
    return _closed_sample("high_res_sample.mp4")


@pytest.fixture
def high_res_video_webm():
    return _closed_sample("high_res_sample.webm")


@pytest.fixture
def low_res_ogv_video():
    return _closed_sample("sample.ogv")


@pytest.fixture
def bad_video():
    local_path = os.path.join("tests", "testcontent", "generated", "bad_video.mp4")
    if not os.path.exists(local_path):
        with open(local_path, "wb") as f:
            f.write(b"novideohere. so ffmpeg should error out!")
            f.flush()
    else:
        f = open(local_path, "rb")
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute


def make_video_file(video_file_file, language="en", ffmpeg_settings=None):
    """
    Creates a VideoFile object with path taken from `video_file_file.name`.
    """
    return VideoFile(
        video_file_file.name, language=language, ffmpeg_settings=ffmpeg_settings
    )


""" *********** TEST BASIC VIDEO PROCESSING  *********** """


class Test_video_processing_and_presets(object):
    def setup_method(self):
        _clear_ricecookerfilecache()

    def test_basic_video_processing_low_res(self, low_res_video):
        expected_video_filename = sample_hash_filename("low_res_sample.mp4")
        video_file = make_video_file(low_res_video)
        video_filename = video_file.process_file()
        assert video_filename == expected_video_filename, (
            "Video file should have filename {}".format(expected_video_filename)
        )
        video_path = config.get_storage_path(video_filename)
        assert os.path.isfile(video_path), "Video should be stored at {}".format(
            video_path
        )
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )

    def test_basic_video_processing_low_res_webm(self, low_res_video_webm):
        expected_video_filename = sample_hash_filename("low_res_sample.webm")
        video_file = make_video_file(low_res_video_webm)
        video_filename = video_file.process_file()
        assert video_filename == expected_video_filename, (
            "Video file should have filename {}".format(expected_video_filename)
        )
        video_path = config.get_storage_path(video_filename)
        assert os.path.isfile(video_path), "Video should be stored at {}".format(
            video_path
        )
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )

    def test_basic_video_processing_high_res(self, high_res_video):
        expected_video_filename = sample_hash_filename("high_res_sample.mp4")
        video_file = make_video_file(high_res_video)
        video_filename = video_file.process_file()
        assert video_filename == expected_video_filename, (
            "Video file should have filename {}".format(expected_video_filename)
        )
        assert video_file.get_preset() == format_presets.VIDEO_HIGH_RES, (
            "Should have high res preset"
        )

    def test_basic_video_processing_high_res_webm(self, high_res_video_webm):
        expected_video_filename = sample_hash_filename("high_res_sample.webm")
        video_file = make_video_file(high_res_video_webm)
        video_filename = video_file.process_file()
        assert video_filename == expected_video_filename, (
            "Video file should have filename {}".format(expected_video_filename)
        )
        assert video_file.get_preset() == format_presets.VIDEO_HIGH_RES, (
            "Should have high res preset"
        )


""" *********** TEST VIDEO COMPRESSION  *********** """


def get_resolution(videopath):
    """Helper function to get resolution of video at videopath."""
    result = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_entries",
            "stream=width,height",
            "-of",
            "default=noprint_wrappers=1",
            str(videopath),
        ]
    )
    pattern = re.compile("width=([0-9]*)[^height]+height=([0-9]*)")
    m = pattern.search(str(result))
    width, height = int(m.group(1)), int(m.group(2))
    return width, height


class Test_video_compression(object):
    def setup_method(self):
        _clear_ricecookerfilecache()

    def test_default_compression_works(self, high_res_video):
        video_file = make_video_file(high_res_video, ffmpeg_settings={"crf": 33})
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 480, "should compress to 480 v resolution by defualt"
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )

    def test_compression_works(self, high_res_video):
        video_file = make_video_file(
            high_res_video, ffmpeg_settings={"crf": 33, "max_height": 300}
        )
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 300, "should be compress to 300 v resolution"
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )

    def test_compression_max_width_works(self, high_res_video):
        video_file = make_video_file(
            high_res_video, ffmpeg_settings={"crf": 33, "max_width": 200}
        )
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert width == 200, "should be compress to 200 hz resolution"
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )

    def test_handles_bad_file(self, bad_video):
        video_file = make_video_file(bad_video, ffmpeg_settings={"crf": 33})
        video_filename = video_file.process_file()
        assert video_filename is None, (
            "Should return None if trying to compress bad file"
        )
        assert video_file in config.FAILED_FILES, (
            "Video file sould be added to config.FAILED_FILES"
        )


def _use_chef_pipeline(monkeypatch, argv=(), settings=None):
    _clear_ricecookerfilecache()
    monkeypatch.setattr(sys, "argv", ["sushichef.py", "--token=t", *argv])
    chef = SushiChef()
    chef.SETTINGS.update(settings or {})
    chef.parse_args_and_options()
    monkeypatch.setattr(config, "FILE_PIPELINE", chef.build_file_pipeline())


def _processed_height(video_file):
    return get_resolution(config.get_storage_path(video_file.process_file()))[1]


@pytest.mark.parametrize(
    "argv,settings,ffmpeg_settings",
    [
        ([], {}, None),
        ([], {}, {"crf": 20}),
        (["--compress"], {"compress": False}, None),
    ],
)
def test_chef_compresses_video_to_720p(
    monkeypatch, high_res_video, argv, settings, ffmpeg_settings
):
    _use_chef_pipeline(monkeypatch, argv, settings)
    video_file = make_video_file(high_res_video, ffmpeg_settings=ffmpeg_settings)
    assert _processed_height(video_file) == 720


def test_chef_compression_keeps_file_crf(monkeypatch, high_res_video):
    _use_chef_pipeline(monkeypatch)
    default, crf20 = (
        os.path.getsize(
            config.get_storage_path(
                make_video_file(high_res_video, ffmpeg_settings=s).process_file()
            )
        )
        for s in (None, {"crf": 20})
    )
    assert crf20 > default


@pytest.mark.parametrize("ffmpeg_settings", [None, {"crf": 20}])
@pytest.mark.parametrize(
    "argv,settings",
    [(["--no-compress"], {"compress": True}), ([], {"compress": False})],
)
def test_chef_without_compression_uploads_video_as_is(
    monkeypatch, caplog, high_res_video, argv, settings, ffmpeg_settings
):
    with caplog.at_level(logging.WARNING):
        _use_chef_pipeline(monkeypatch, argv, settings)
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "Compression is off: media is uploaded uncompressed."
    ]
    video_file = make_video_file(high_res_video, ffmpeg_settings=ffmpeg_settings)
    assert video_file.process_file() == sample_hash_filename("high_res_sample.mp4")
    mov_file = VideoFile(sample_path("sample.mov"), ffmpeg_settings=ffmpeg_settings)
    assert _processed_height(mov_file) == 720


def test_chef_without_ffmpeg_uploads_supported_media_as_is(
    monkeypatch, caplog, empty_path, channel
):
    samples = ["high_res_sample.mp4", "high_res_sample.webm", "sample_audio.mp3"]
    nodes = {}
    for sample in samples + ["sample.mov"]:
        nodes[sample] = ContentNode(
            source_id=sample,
            title=sample,
            license=licenses.CC_BY,
            copyright_holder="Holder",
            uri=sample_path(sample),
        )
        channel.add_child(nodes[sample])

    monkeypatch.setattr(config, "STRICT", False)
    with caplog.at_level(logging.WARNING):
        _use_chef_pipeline(monkeypatch)
        filenames = ChannelManager(channel).process_tree()

    assert sorted(filenames) == sorted(sample_hash_filename(s) for s in samples)
    assert nodes["sample.mov"].valid is False
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings[:3] == [
        "ffmpeg and ffprobe are both needed for compression: media is uploaded uncompressed.",
        "ffmpeg not found: media is uploaded unverified.",
        "ffprobe not found: media duration and video resolution are not detected.",
    ]
    assert [w.split(" ")[0] for w in warnings[3:]] == ["sample.mov"]


def test_chef_without_compression_or_ffmpeg_warns_unverified(
    monkeypatch, caplog, empty_path
):
    with caplog.at_level(logging.WARNING):
        _use_chef_pipeline(monkeypatch, ["--no-compress"])
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "Compression is off: media is uploaded uncompressed.",
        "ffmpeg not found: media is uploaded unverified.",
        "ffprobe not found: media duration and video resolution are not detected.",
    ]


def test_chef_without_ffprobe_uploads_supported_media_as_is(
    monkeypatch, caplog, tmp_path
):
    bin_dir = tmp_path / "ffmpeg-only"
    bin_dir.mkdir()
    shutil.copy(shutil.which("ffmpeg"), bin_dir)
    with monkeypatch.context() as no_ffprobe:
        no_ffprobe.setenv("PATH", str(bin_dir))
        with caplog.at_level(logging.WARNING):
            _use_chef_pipeline(monkeypatch)
        assert [
            r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
        ] == [
            "ffmpeg and ffprobe are both needed for compression: media is uploaded uncompressed.",
            "ffprobe not found: media duration and video resolution are not detected.",
        ]
        webm_file = VideoFile(sample_path("high_res_sample.webm"))
        assert webm_file.process_file() == sample_hash_filename("high_res_sample.webm")
        without_ffprobe = VideoFile(sample_path("sample.mov")).process_file()
        assert without_ffprobe.endswith(".webm")
        rerun = VideoFile(sample_path("sample.mov")).process_file()
        assert rerun == without_ffprobe

    with_ffprobe = VideoFile(sample_path("sample.mov")).process_file()
    assert with_ffprobe
    assert with_ffprobe != without_ffprobe


def test_media_processed_without_ffmpeg_is_reprocessed_with_it(
    monkeypatch, tmp_path, high_res_video
):
    truncated = tmp_path / "truncated.mp4"
    data = Path(high_res_video.name).read_bytes()
    truncated.write_bytes(data[: len(data) // 3])
    with monkeypatch.context() as no_tools:
        no_tools.setenv("PATH", str(tmp_path))
        _use_chef_pipeline(monkeypatch)
        assert VideoFile(str(truncated)).process_file()
        assert make_video_file(high_res_video).process_file()

    monkeypatch.setattr(config, "FAILED_FILES", [])
    truncated_file = VideoFile(str(truncated))
    assert truncated_file.process_file() is None
    assert config.FAILED_FILES == [truncated_file]
    assert "moov atom not found" in truncated_file.error
    video_file = make_video_file(high_res_video)
    video_file.process_file()
    assert video_file.get_preset() == format_presets.VIDEO_HIGH_RES
    assert video_file.duration == 1


def _process_uri(path, context):
    node = ContentNode(
        source_id="video",
        title="Video",
        license=licenses.CC_BY,
        copyright_holder="Holder",
        uri=path,
        context=context,
    )
    node.process_files()
    [video_file] = node.files
    return video_file.filename


@pytest.mark.parametrize(
    "sample,process",
    [
        (
            "high_res_sample.mp4",
            lambda path: VideoFile(path, ffmpeg_settings=False).process_file(),
        ),
        (
            "sample_audio.mp3",
            lambda path: AudioFile(path, ffmpeg_settings=False).process_file(),
        ),
        ("high_res_sample.mp4", lambda path: _process_uri(path, {"compress": False})),
    ],
)
def test_file_opted_out_of_compression_is_unchanged(monkeypatch, sample, process):
    _use_chef_pipeline(monkeypatch)
    assert process(sample_path(sample)) == sample_hash_filename(sample)


""" *********** TEST VIDEO CONVERSION  *********** """


class Test_video_conversion(object):
    def setup_method(self):
        _clear_ricecookerfilecache()

    def test_convert_ogv_works(self, low_res_ogv_video):
        video_file = make_video_file(
            low_res_ogv_video, ffmpeg_settings={"crf": 33, "max_height": 300}
        )
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 300, "should be compress to 300 v resolution"
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )

    def test_convert_and_resize_ogv_works(self, low_res_ogv_video):
        video_file = make_video_file(
            low_res_ogv_video, ffmpeg_settings={"crf": 33, "max_height": 200}
        )
        video_filename = video_file.process_file()
        video_path = config.get_storage_path(video_filename)
        width, height = get_resolution(video_path)
        assert height == 200, "should be compress to 200 v resolution"
        assert video_file.get_preset() == format_presets.VIDEO_LOW_RES, (
            "Should have low res preset"
        )


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
    video_node = VideoNode("vid-src-id", "Video", licenses.PUBLIC_DOMAIN)
    video_node.add_file(video_file)
    sub1 = SubtitleFile(local_path, language="en")
    video_node.add_file(sub1)
    sub2 = SubtitleFile(local_path, language="ar")
    video_node.add_file(sub2)
    video_node.validate()
    sub_files = [f for f in video_node.files if isinstance(f, SubtitleFile)]
    assert len(sub_files) == 2, "Missing subtitles files!"


def test_duplicate_language_codes_fixed_by_validate(video_file):
    """
    Video nodes should have at most one subtitle file for a particular lang code.
    """
    local_path = os.path.join("tests", "testcontent", "samples", "testsubtitles_ar.srt")
    assert os.path.exists(local_path)
    video_node = VideoNode("vid-src-id", "Video", licenses.PUBLIC_DOMAIN)
    video_node.add_file(video_file)
    sub1 = SubtitleFile(local_path, language="ar")
    video_node.add_file(sub1)
    # now let's add file with a duplicate language code...
    sub2 = SubtitleFile(local_path, language="ar")
    video_node.add_file(sub2)
    video_node.validate()
    sub_files = [f for f in video_node.files if isinstance(f, SubtitleFile)]
    assert len(sub_files) == 1, "Duplicate subtitles files not removed!"
