from __future__ import print_function

import atexit
import os
import tempfile

import pytest
import requests_cache
from conftest import download_fixture_file

from ricecooker.utils import audio
from ricecooker.utils import videos


# cache, so we don't keep requesting the full audio
requests_cache.install_cache("audio_cache")


# FIXTURES
################################################################################


@pytest.fixture
def audio_file():
    source_url = "https://archive.org/download/sound247/sound247.mp3"
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "testcontent",
            "downloaded",
            "audio_media_test.mp3",
        )
    )
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    f = open(local_path, "rb")
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute


@pytest.fixture
def bad_audio():
    with TempFile(suffix=".mp3") as f:
        f.write(b"noaudiohere. ffmpeg soshould error")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor


# TESTS
################################################################################


class Test_compress_video:
    def test_compression_works(self, audio_file):
        duration = videos.extract_duration_of_media(audio_file.name, "mp3")
        with TempFile(suffix=".mp3") as vout:
            audio.compress_audio(audio_file.name, vout.name, overwrite=True)
            compressed_duration = videos.extract_duration_of_media(vout.name, "mp3")
            assert duration == compressed_duration

    def test_raises_for_bad_file(self, bad_audio):
        with TempFile(suffix=".mp4") as vout:
            with pytest.raises(audio.AudioCompressionError):
                audio.compress_audio(bad_audio.name, vout.name, overwrite=True)


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
