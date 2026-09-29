from __future__ import print_function

import atexit
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time

import pytest
from conftest import sample_path
from le_utils.constants import format_presets

from ricecooker.utils import videos

# FIXTURES
################################################################################


def _closed_sample(*parts):
    """Open and close a committed sample so tests can use its ``.name`` attribute."""
    f = open(sample_path(*parts), "rb")
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute


@pytest.fixture
def low_res_video():
    return _closed_sample("low_res_sample.mp4")


@pytest.fixture
def high_res_video():
    return _closed_sample("high_res_sample.mp4")


@pytest.fixture
def low_res_video_webm():
    return _closed_sample("low_res_sample.webm")


@pytest.fixture
def high_res_video_webm():
    return _closed_sample("high_res_sample.webm")


@pytest.fixture
def low_res_ogv_video():
    return _closed_sample("sample.ogv")


@pytest.fixture
def high_res_mov_video():
    return _closed_sample("sample.mov")


@pytest.fixture
def bad_video():
    # A tiny local garbage file; imported by test_thumbnails for its error path.
    with TempFile(suffix=".mp4") as f:
        f.write(b"novideohere. ffmpeg soshould error")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor


# TESTS
################################################################################


class Test_check_video_resolution:
    def test_returns_a_format_preset(self, low_res_video):
        preset = videos.guess_video_preset_by_resolution(low_res_video.name)
        assert preset in [
            format_presets.VIDEO_HIGH_RES,
            format_presets.VIDEO_LOW_RES,
            format_presets.VIDEO_VECTOR,
        ]

    def test_detects_low_res_videos(self, low_res_video):
        preset = videos.guess_video_preset_by_resolution(low_res_video.name)
        assert preset == format_presets.VIDEO_LOW_RES

    def test_detects_high_res_videos(self, high_res_video):
        preset = videos.guess_video_preset_by_resolution(high_res_video.name)
        assert preset == format_presets.VIDEO_HIGH_RES

    def test_detects_low_res_videos_webm(self, low_res_video_webm):
        preset = videos.guess_video_preset_by_resolution(low_res_video_webm.name)
        assert preset == format_presets.VIDEO_LOW_RES

    def test_detects_high_res_videos_webm(self, high_res_video_webm):
        preset = videos.guess_video_preset_by_resolution(high_res_video_webm.name)
        assert preset == format_presets.VIDEO_HIGH_RES

    def test_hung_probe_falls_back_to_low_res(
        self, low_res_video, stub_on_path, monkeypatch
    ):
        stub_on_path("ffprobe")
        monkeypatch.setattr(videos, "PROBE_TIMEOUT", 1)
        start = time.monotonic()
        preset = videos.guess_video_preset_by_resolution(low_res_video.name)
        assert preset == format_presets.VIDEO_LOW_RES
        assert time.monotonic() - start < 10


class Test_extract_duration_of_media:
    def test_unknown_duration_falls_back_to_decoding(
        self, high_res_video, stub_on_path
    ):
        stub_on_path("ffprobe", "echo N/A")
        assert videos.extract_duration_of_media(high_res_video.name, "mp4") == 1


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


class Test_compress_video:
    def test_compression_works(self, high_res_video):
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(high_res_video.name, vout.name, overwrite=True)
            width, height = get_resolution(vout.name)
            assert height == 480, "should compress to 480 v resolution by default"

    def test_compression_max_width(self, high_res_video):
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(
                high_res_video.name, vout.name, overwrite=True, max_width=120
            )
            width, height = get_resolution(vout.name)
            assert width == 120, "should be 120 h resolution since max_width set"

    def test_compression_max_width_odd(self, high_res_video):
        """
        regression test for: https://github.com/learningequality/pressurecooker/issues/11
        """
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(
                high_res_video.name, vout.name, overwrite=True, max_width=121
            )
            width, height = get_resolution(vout.name)
            assert width == 120, (
                "should round down to 120 h resolution when max_width=121 set"
            )

    def test_compression_max_height(self, high_res_video):
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(
                high_res_video.name, vout.name, overwrite=True, max_height=140
            )
            width, height = get_resolution(vout.name)
            assert height == 140, "should be 140 v resolution since max_height set"

    def test_raises_for_bad_file(self, bad_video):
        with TempFile(suffix=".mp4") as vout:
            with pytest.raises(videos.VideoCompressionError):
                videos.compress_video(bad_video.name, vout.name, overwrite=True)

    def test_faststart_stall_raises(self, high_res_video, stub_on_path, monkeypatch):
        stub_on_path("ffmpeg")
        monkeypatch.setattr(videos, "STALL_TIMEOUT", 1)
        with TempFile(suffix=".mp4") as vout:
            with pytest.raises(subprocess.TimeoutExpired):
                videos.web_faststart_video(
                    high_res_video.name, vout.name, overwrite=True
                )

    def test_default_compression_works_webm(self, high_res_video_webm):
        with TempFile(suffix=".webm") as vout:
            videos.compress_video(high_res_video_webm.name, vout.name, overwrite=True)
            width, height = get_resolution(vout.name)
            assert height == 480, "should compress to 480 v resolution by default"

    def test_compression_works_webm(self, high_res_video_webm):
        with TempFile(suffix=".webm") as vout:
            videos.compress_video(
                high_res_video_webm.name, vout.name, overwrite=True, max_height=300
            )
            width, height = get_resolution(vout.name)
            assert height == 300, "should be compress to 300 v resolution"

    def test_compression_max_width_works_webm(self, high_res_video_webm):
        with TempFile(suffix=".webm") as vout:
            videos.compress_video(
                high_res_video_webm.name, vout.name, overwrite=True, max_width=200
            )
            width, height = get_resolution(vout.name)
            assert width == 200, "should be compress to 200 hz resolution"

    def test_compression_format_conversion_to_webm(self, high_res_video):
        with TempFile(suffix=".webm") as vout:
            videos.compress_video(
                high_res_video.name, vout.name, overwrite=True, max_height=300
            )
            width, height = get_resolution(vout.name)
            assert height == 300, "should be compress to 300 v resolution"

    def test_compression_webm_to_mp4_conversion(self, high_res_video_webm):
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(
                high_res_video_webm.name, vout.name, overwrite=True, max_height=300
            )
            width, height = get_resolution(vout.name)
            assert height == 300, "should be compress to 300 v resolution"


class Test_convert_video:
    def test_convert_mov_works(self, high_res_mov_video):
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(high_res_mov_video.name, vout.name, overwrite=True)
            width, height = get_resolution(vout.name)
            assert height == 480, "should convert .ogv to .mp4 and set 480 v res"

    def test_convert_and_resize_ogv_works(self, low_res_ogv_video):
        with TempFile(suffix=".mp4") as vout:
            videos.compress_video(
                low_res_ogv_video.name, vout.name, overwrite=True, max_height=200
            )
            width, height = get_resolution(vout.name)
            assert height == 200, "should convert .ogv to .mp4 and set 200 v res"


class Test_run_ffmpeg:
    def test_progressing_run_outlives_stall_timeout(self, monkeypatch, high_res_video):
        monkeypatch.setattr(videos, "STALL_TIMEOUT", 2)
        result = videos.run_ffmpeg(
            ["-stream_loop", "4", "-re", "-i", high_res_video.name, "-f", "null", "-"]
        )
        assert result.returncode == 0
        assert "progress=end" in result.stdout

    def test_large_stderr_does_not_stall(self, monkeypatch, high_res_video):
        monkeypatch.setattr(videos, "STALL_TIMEOUT", 2)
        result = videos.run_ffmpeg(
            [
                "-v",
                "trace",
                "-stream_loop",
                "29",
                "-i",
                high_res_video.name,
                "-f",
                "null",
                "-",
            ]
        )
        assert result.returncode == 0
        assert len(result.stderr) > 65536

    @pytest.mark.skipif(sys.platform == "win32", reason="needs os.mkfifo")
    def test_stalled_run_is_killed(self, monkeypatch, tmp_path):
        fifo = tmp_path / "stalled.pcm"
        os.mkfifo(fifo)
        release = threading.Event()

        def feed():
            with open(fifo, "wb") as fh:
                fh.write(bytes(64000))
                fh.flush()
                release.wait(10)

        threading.Thread(target=feed, daemon=True).start()
        monkeypatch.setattr(videos, "STALL_TIMEOUT", 1)
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                videos.run_ffmpeg(
                    [
                        "-f",
                        "s16le",
                        "-ar",
                        "8000",
                        "-ac",
                        "1",
                        "-i",
                        str(fifo),
                        "-f",
                        "null",
                        "-",
                    ]
                )
        finally:
            release.set()

    def test_stall_returns_while_wrapper_child_holds_pipes(
        self, stub_on_path, monkeypatch
    ):
        stub_on_path("ffmpeg", "sleep 10")
        monkeypatch.setattr(videos, "STALL_TIMEOUT", 1)
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            videos.run_ffmpeg([])
        assert time.monotonic() - start < 5

    @pytest.mark.parametrize("sig", ["SIGINT", "SIGHUP"])
    def test_terminal_signal_reaches_ffmpeg_on_worker_thread(
        self, stub_on_path, tmp_path, sig
    ):
        pidfile = tmp_path / "ffmpeg.pid"
        stub_on_path("ffmpeg", f"echo $$ > {pidfile}; exec sleep 30")
        chef = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from concurrent.futures import ThreadPoolExecutor\n"
                "from ricecooker.utils import videos\n"
                "ThreadPoolExecutor().submit(videos.run_ffmpeg, []).result()\n",
            ],
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 10
            while not pidfile.exists() or not pidfile.read_text().strip():
                assert time.monotonic() < deadline
                time.sleep(0.1)
            os.killpg(chef.pid, getattr(signal, sig))
            chef.wait(10)
        finally:
            chef.kill()
        deadline = time.monotonic() + 5
        with pytest.raises(ProcessLookupError):
            while time.monotonic() < deadline:
                os.kill(int(pidfile.read_text()), 0)
                time.sleep(0.1)

    def test_interrupt_kills_ffmpeg(self, stub_on_path, tmp_path):
        pidfile = tmp_path / "ffmpeg.pid"
        stub_on_path("ffmpeg", f"echo $$ > {pidfile}; exec sleep 30")
        interrupt = threading.Timer(1, os.kill, (os.getpid(), signal.SIGINT))
        interrupt.start()
        try:
            with pytest.raises(KeyboardInterrupt):
                videos.run_ffmpeg([])
        finally:
            interrupt.cancel()
        with pytest.raises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)


# Helper class for cross-platform temporary files
################################################################################


def remove_temp_file(*args, **kwargs):
    filename = args[0]
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass
    assert not os.path.exists(filename)


class TempFile(object):
    """
    tempfile.NamedTemporaryFile deletes the file as soon as the filehandle is closed.
    This is OK on unix but on Windows the file can't be used by other commands
    (i.e. ffmpeg) unti the file is closed.
    Temporary files are instead deleted when we quit.
    """

    def __init__(self, *args, **kwargs):
        # all parameters will be passed to NamedTemporaryFile
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        # create a temporary file as per usual, but set it up to be deleted once we're done
        self.f = tempfile.NamedTemporaryFile(*self.args, delete=False, **self.kwargs)
        atexit.register(remove_temp_file, self.f.name)
        return self.f

    def __exit__(self, _type, value, traceback):
        self.f.close()


@pytest.fixture
def corrupt_media_path():
    # Create a corrupt file
    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
        f.write(b"This is not a valid media file")
        yield f.name


def test_validate_video_file_valid(video_file):
    is_valid, error = videos.validate_media_file(video_file.path)
    assert is_valid
    assert error == ""


def test_validate_audio_file_valid(audio_file):
    is_valid, error = videos.validate_media_file(audio_file.path)
    assert is_valid
    assert error == ""


def test_validate_media_file_nonexistent():
    is_valid, error = videos.validate_media_file("nonexistent_file.mp4")
    assert not is_valid
    assert error and "\n" not in error
    assert "nonexistent_file.mp4" not in error


def test_validate_media_file_reports_cause(tmp_path, low_res_video):
    with open(low_res_video.name, "rb") as f:
        data = f.read()
    media = tmp_path / "bad.mp4"
    media.write_bytes(data[: len(data) // 2])

    is_valid, error = videos.validate_media_file(str(media))
    assert not is_valid
    assert error == "moov atom not found"


def test_validate_media_file_reports_cause_not_probe_noise(tmp_path):
    bad_webm = tmp_path / "bad.webm"
    bad_webm.write_bytes(b"not media")

    is_valid, error = videos.validate_media_file(str(bad_webm))
    assert not is_valid
    # ffmpeg < 6.1 fails before the matroska demuxer runs, so only the
    # untagged probe line is ruled out.
    assert not error.startswith("Truncating packet")


@pytest.mark.skipif(sys.platform == "win32", reason="stand-in ffmpeg is a shell script")
@pytest.mark.parametrize(
    "script,expected",
    [
        ("exit 1", "ffmpeg could not decode the file"),
        (
            'while [ "$1" != -i ]; do shift; done; echo "$2: Invalid data found when processing input" >&2; exit 1',
            "Invalid data found when processing input",
        ),
    ],
)
def test_validate_media_file_stand_in_ffmpeg(
    tmp_path, monkeypatch, corrupt_media_path, script, expected
):
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text(f"#!/bin/sh\n{script}\n")
    fake_ffmpeg.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)

    is_valid, error = videos.validate_media_file(corrupt_media_path)
    assert not is_valid
    assert error == expected
