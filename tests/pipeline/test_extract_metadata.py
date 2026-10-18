"""Tests for metadata extraction in the file pipeline."""

import os
import shutil
import subprocess
import tempfile
import zipfile

import pytest
from cachecontrol.caches.file_cache import FileCache
from le_utils.constants import content_kinds
from le_utils.constants import format_presets

from ricecooker import config
from ricecooker.utils import caching
from ricecooker.utils import videos
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.extract_metadata import AudioMetadataExtractor
from ricecooker.utils.pipeline.extract_metadata import VideoMetadataExtractor


def _create_archive(path, files_dict):
    """Helper to create a zip archive with given files."""
    with zipfile.ZipFile(path, "w") as zf:
        for filename, content in files_dict.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(filename, content)


class TestKPUBMetadataExtraction:
    """Tests for KPUB metadata extraction."""

    def test_kpub_metadata(self):
        """KPUB files should be detected with correct preset and kind."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.kpub")
            _create_archive(
                path,
                {"index.html": "<html><body><p>Hello</p></body></html>"},
            )

            pipeline = FilePipeline()
            result = pipeline.execute(path)[0]

            assert result.preset == format_presets.KPUB_ZIP
            assert result.content_node_metadata is not None
            assert result.content_node_metadata["kind"] == content_kinds.DOCUMENT


def test_hung_duration_decode_fails_file(audio_file, stub_on_path, monkeypatch):
    stub_on_path("ffprobe", "echo N/A")
    stub_on_path("ffmpeg")
    monkeypatch.setattr(videos, "STALL_TIMEOUT", 1)
    with pytest.raises(InvalidFileException, match="ffmpeg timed out"):
        AudioMetadataExtractor().execute(audio_file.path, skip_cache=True)


def test_hung_ffprobe_fails_file(video_file, stub_on_path, monkeypatch):
    stub_on_path("ffprobe")
    monkeypatch.setattr(videos, "PROBE_TIMEOUT", 1)
    with pytest.raises(InvalidFileException, match="ffprobe timed out"):
        VideoMetadataExtractor().execute(video_file.path, skip_cache=True)


@pytest.mark.parametrize("missing_tool", ["ffmpeg", "ffprobe"])
def test_duration_skipped_without_media_tool_is_redetected_with_it(
    monkeypatch, tmp_path, missing_tool
):
    monkeypatch.setattr(caching, "FILECACHE", FileCache(str(tmp_path / "cache")))
    path = config.get_storage_path("no-{}-duration.webm".format(missing_tool))
    # A webm muxed to a pipe has no duration header, so ffprobe reports N/A.
    with open(path, "wb") as out:
        subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "testsrc=s=64x64:d=1"]
            + ["-c:v", "libvpx", "-f", "webm", "pipe:1"],
            stdout=out,
            check=True,
        )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    present_tool = "ffprobe" if missing_tool == "ffmpeg" else "ffmpeg"
    shutil.copy(shutil.which(present_tool), bin_dir)
    with monkeypatch.context() as one_tool:
        one_tool.setenv("PATH", str(bin_dir))
        [result] = VideoMetadataExtractor().execute(path)
        assert result.duration is None
    [result] = VideoMetadataExtractor().execute(path)
    assert result.duration is not None
