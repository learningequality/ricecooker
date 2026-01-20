"""Tests for metadata extraction in the file pipeline."""
import os
import tempfile
import zipfile

from le_utils.constants import content_kinds
from le_utils.constants import format_presets

from ricecooker.utils.pipeline import FilePipeline


def _create_archive(path, files_dict):
    """Helper to create a zip archive with given files."""
    with zipfile.ZipFile(path, "w") as zf:
        for filename, content in files_dict.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(filename, content)


class TestKPUBMetadataExtraction:
    """Tests for KPUB metadata extraction."""

    def test_kpub_preset_detected(self):
        """KPUB files should be detected with the correct preset."""
        temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
        temp_archive.close()

        try:
            _create_archive(
                temp_archive.name,
                {"index.html": "<html><body><p>Hello</p></body></html>"},
            )

            pipeline = FilePipeline()
            results = pipeline.execute(temp_archive.name)
            result = results[0]

            assert result.preset == format_presets.KPUB_ZIP
        finally:
            os.unlink(temp_archive.name)

    def test_kpub_kind_detected(self):
        """KPUB files should be detected with DOCUMENT kind."""
        temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
        temp_archive.close()

        try:
            _create_archive(
                temp_archive.name,
                {"index.html": "<html><body><p>Hello</p></body></html>"},
            )

            pipeline = FilePipeline()
            results = pipeline.execute(temp_archive.name)
            result = results[0]

            assert result.content_node_metadata is not None
            assert result.content_node_metadata["kind"] == content_kinds.DOCUMENT
        finally:
            os.unlink(temp_archive.name)
