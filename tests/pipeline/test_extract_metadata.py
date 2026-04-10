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
