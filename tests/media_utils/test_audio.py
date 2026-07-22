from __future__ import print_function

import atexit
import os
import subprocess
import tempfile
from unittest import mock

import pytest
from conftest import sample_path

from ricecooker.utils import audio
from ricecooker.utils import videos

# FIXTURES
################################################################################


@pytest.fixture
def audio_file():
    f = open(sample_path("sample_audio.mp3"), "rb")
    f.close()
    return f  # returns a closed file descriptor which we use for name attribute


# TESTS
################################################################################


class Test_compress_video:
    def test_compression_works(self, audio_file):
        duration = videos.extract_duration_of_media(audio_file.name, "mp3")
        with TempFile(suffix=".mp3") as vout:
            audio.compress_audio(audio_file.name, vout.name, overwrite=True)
            compressed_duration = videos.extract_duration_of_media(vout.name, "mp3")
            assert duration == compressed_duration

    def test_raises_for_bad_file(self):
        # ffmpeg failure is mocked so the error-mapping path is exercised without
        # shelling out to a real encoder.
        with TempFile(suffix=".mp4") as vout:
            with mock.patch(
                "ricecooker.utils.audio.subprocess.check_output",
                side_effect=subprocess.CalledProcessError(1, "ffmpeg", b"bad input"),
            ):
                with pytest.raises(audio.AudioCompressionError):
                    audio.compress_audio("source.mp3", vout.name, overwrite=True)


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
