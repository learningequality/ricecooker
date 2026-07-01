"""Tests for audio and video compression in archive files."""

import os
import tempfile
import zipfile
from unittest.mock import patch

import pytest

from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.utils.pipeline.convert import _find_common_root
from ricecooker.utils.pipeline.convert import _find_entry_html
from ricecooker.utils.pipeline.convert import HTML5ConversionHandler
from ricecooker.utils.pipeline.convert import KPUBConversionHandler
from ricecooker.utils.pipeline.exceptions import InvalidFileException


def test_html5_archive_with_mp4_compression(video_file, audio_file):
    """Test that MP4 and MP3 files within HTML5 archives are compressed when compression is enabled."""
    # Create temporary HTML5 archive with media files
    temp_archive = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_archive.close()

    try:
        with zipfile.ZipFile(temp_archive.name, "w") as zf:
            zf.writestr("index.html", "<html><body>Test content</body></html>")
            # Add media files by reading from fixture files
            with open(video_file.path, "rb") as vf:
                zf.writestr("video/sample.mp4", vf.read())
            with open(audio_file.path, "rb") as af:
                zf.writestr("audio/sample.mp3", af.read())

        with (
            patch(
                "ricecooker.utils.pipeline.convert.compress_video"
            ) as mock_video_compress,
            patch(
                "ricecooker.utils.pipeline.convert.compress_audio"
            ) as mock_audio_compress,
        ):
            # Mock successful compression
            mock_video_compress.return_value = None
            mock_audio_compress.return_value = None

            # Process the HTML5 file with compression enabled
            with patch("ricecooker.config.COMPRESS", True):
                html_file = HTMLZipFile(temp_archive.name)
                result = html_file.process_file()

            # Verify both compression functions were called
            assert mock_video_compress.called, (
                "Video compression should be called for MP4 files"
            )
            assert mock_audio_compress.called, (
                "Audio compression should be called for MP3 files"
            )
            assert result is not None, "Processing should succeed"

    finally:
        os.unlink(temp_archive.name)


def test_h5p_archive_with_webm_compression(video_file):
    """Test that WebM files within H5P archives are compressed when compression is enabled."""
    # Create temporary H5P archive with WebM file
    temp_archive = tempfile.NamedTemporaryFile(suffix=".h5p", delete=False)
    temp_archive.close()

    try:
        with zipfile.ZipFile(temp_archive.name, "w") as zf:
            zf.writestr("h5p.json", '{"valid": "json"}')
            zf.writestr("content/content.json", '{"valid": "content"}')
            # Add video file but with .webm extension to test WebM handling
            with open(video_file.path, "rb") as vf:
                zf.writestr("videos/sample.webm", vf.read())

        with patch("ricecooker.utils.pipeline.convert.compress_video") as mock_compress:
            # Mock successful compression
            mock_compress.return_value = None

            # Process the H5P file with compression enabled
            with patch("ricecooker.config.COMPRESS", True):
                h5p_file = H5PFile(temp_archive.name)
                result = h5p_file.process_file()

            # Verify compression was called
            assert mock_compress.called, (
                "Video compression should be called for WebM files"
            )
            assert result is not None, "Processing should succeed"

    finally:
        os.unlink(temp_archive.name)


def test_archive_no_compression_when_disabled(video_file, audio_file):
    """Test that media files are not compressed when compression is disabled."""
    # Create temporary HTML5 archive with media files
    temp_archive = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_archive.close()

    try:
        with zipfile.ZipFile(temp_archive.name, "w") as zf:
            zf.writestr("index.html", "<html><body>Test content</body></html>")
            with open(video_file.path, "rb") as vf:
                zf.writestr("video/sample.mp4", vf.read())
            with open(audio_file.path, "rb") as af:
                zf.writestr("audio/sample.mp3", af.read())

        with (
            patch(
                "ricecooker.utils.pipeline.convert.compress_video"
            ) as mock_video_compress,
            patch(
                "ricecooker.utils.pipeline.convert.compress_audio"
            ) as mock_audio_compress,
        ):
            # Process the HTML5 file with compression disabled
            with patch("ricecooker.config.COMPRESS", False):
                html_file = HTMLZipFile(temp_archive.name)
                result = html_file.process_file()

            # Verify compression functions were not called
            assert not mock_video_compress.called, (
                "Video compression should not be called when disabled"
            )
            assert not mock_audio_compress.called, (
                "Audio compression should not be called when disabled"
            )
            assert result is not None, "Processing should still succeed"

    finally:
        os.unlink(temp_archive.name)


# HTML5 Conversion Tests
# These test the HTML5ConversionHandler validation logic


def _create_archive(path, files_dict):
    """Helper to create a zip archive with given files."""
    with zipfile.ZipFile(path, "w") as zf:
        for filename, content in files_dict.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(filename, content)


class TestHTML5Validation:
    """Regression tests for HTML5ConversionHandler body validation."""

    def _validate(self, files):
        """Create an HTML5 archive with given files and validate it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.zip")
            _create_archive(path, files)
            HTML5ConversionHandler().validate_archive(path)

    def test_empty_body_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)empty"):
            self._validate({"index.html": "<html><body></body></html>"})

    def test_whitespace_only_body_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)empty"):
            self._validate({"index.html": "<html><body>   \n  </body></html>"})

    def test_body_with_child_element_accepted(self):
        self._validate({"index.html": "<html><body><p>Hello</p></body></html>"})

    def test_body_with_text_only_accepted(self):
        self._validate({"index.html": "<html><body>Hello world</body></html>"})


class TestHTML5EntryPoint:
    """Tests for HTML entry point detection and zip denesting,
    mirroring Studio's findFirstHtml/cleanHTML5Zip behavior."""

    VALID_HTML = "<html><body><p>Hello</p></body></html>"

    def _execute(self, files):
        """Create an HTML5 archive with given files and run the handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.zip")
            _create_archive(path, files)
            return HTML5ConversionHandler().execute(path, skip_cache=True)

    def test_find_common_root(self):
        assert _find_common_root([]) == ""
        assert _find_common_root(["index.html"]) == ""
        assert _find_common_root(["dist/index.html"]) == "dist"
        assert _find_common_root(["a/b/x.html", "a/b/y.css"]) == "a/b"
        assert _find_common_root(["a/b/x.html", "a/c/y.css"]) == "a"
        assert _find_common_root(["a/x.html", "y.css"]) == ""

    def test_find_entry_html(self):
        # index.html at the root is preferred
        assert _find_entry_html(["other.html", "index.html"]) == "index.html"
        # then index.html relative to the common root
        assert (
            _find_entry_html(["dist/other.html", "dist/index.html"])
            == "dist/index.html"
        )
        # then any index.html
        assert _find_entry_html(["main.html", "sub/index.html"]) == "sub/index.html"
        # then the shallowest html file
        assert _find_entry_html(["b/page.html", "a.html"]) == "a.html"
        # no html files at all
        assert _find_entry_html(["style.css", "script.js"]) is None

    def test_no_html_file_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)no HTML file"):
            self._execute({"script.js": "console.log('hello');"})

    def test_non_index_entry_accepted_and_recorded(self):
        results = self._execute(
            {"app.html": self.VALID_HTML, "script.js": "console.log('hello');"}
        )
        assert results[0].content_node_metadata.extra_fields == {
            "options": {"entry": "app.html"}
        }

    def test_non_index_entry_body_validated(self):
        with pytest.raises(InvalidFileException, match="(?i)empty"):
            self._execute({"app.html": "<html><body></body></html>"})

    def test_root_index_entry_not_recorded(self):
        results = self._execute({"index.html": self.VALID_HTML})
        assert results[0].content_node_metadata is None

    def test_nested_archive_denested(self):
        results = self._execute(
            {
                "dist/index.html": self.VALID_HTML,
                "dist/css/style.css": "body { color: red; }",
            }
        )
        # The common root is stripped, so index.html ends up at the root
        # and no entry point needs to be recorded.
        assert results[0].content_node_metadata is None
        with zipfile.ZipFile(results[0].path) as zf:
            names = set(zf.namelist())
        assert "index.html" in names
        assert "css/style.css" in names

    def test_nested_non_index_entry_denested_and_recorded(self):
        results = self._execute({"dist/app.html": self.VALID_HTML})
        assert results[0].content_node_metadata.extra_fields == {
            "options": {"entry": "app.html"}
        }
        with zipfile.ZipFile(results[0].path) as zf:
            assert "app.html" in zf.namelist()


class TestKPUBValidation:
    """Tests for KPUBConversionHandler validation."""

    def _validate(self, files):
        """Create a KPUB archive with given files and validate it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.kpub")
            _create_archive(path, files)
            KPUBConversionHandler().validate_archive(path)

    def test_valid_archive(self):
        self._validate({"index.html": "<html><body><p>Hello world</p></body></html>"})

    def test_missing_index_html(self):
        with pytest.raises(InvalidFileException, match="(?i)index.html"):
            self._validate({"content.html": "<html><body><p>Hello</p></body></html>"})

    def test_javascript_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)javascript"):
            self._validate(
                {
                    "index.html": "<html><body><p>Hello</p></body></html>",
                    "script.js": "console.log('hello');",
                }
            )

    def test_css_file_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)css"):
            self._validate(
                {
                    "index.html": "<html><body><p>Hello</p></body></html>",
                    "styles.css": "body { color: red; }",
                }
            )

    def test_inline_script_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)javascript"):
            self._validate(
                {
                    "index.html": "<html><body><p>Hello</p><script>alert('hi');</script></body></html>",
                }
            )

    def test_inline_styles_allowed(self):
        self._validate(
            {"index.html": '<html><body><p style="color: red;">Hello</p></body></html>'}
        )

    def test_images_allowed(self):
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self._validate(
            {
                "index.html": '<html><body><img src="image.png"></body></html>',
                "image.png": png_data,
            }
        )

    def test_empty_body_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)empty"):
            self._validate({"index.html": "<html><body></body></html>"})

    def test_whitespace_only_body_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)empty"):
            self._validate({"index.html": "<html><body>   \n  </body></html>"})

    def test_invalid_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.kpub")
            with open(path, "wb") as f:
                f.write(b"not a zip file")
            with pytest.raises(InvalidFileException, match="(?i)zip"):
                KPUBConversionHandler().validate_archive(path)
