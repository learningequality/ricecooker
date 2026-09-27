"""Tests for metadata extraction in the file pipeline."""

import os
import tempfile
import zipfile

import pytest
from le_utils.constants import content_kinds
from le_utils.constants import format_presets

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
