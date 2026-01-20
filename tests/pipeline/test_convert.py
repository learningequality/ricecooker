"""Tests for audio and video compression in archive files."""
import os
import tempfile
import zipfile
from unittest.mock import patch

import pytest

from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile
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

        with patch(
            "ricecooker.utils.pipeline.convert.compress_video"
        ) as mock_video_compress, patch(
            "ricecooker.utils.pipeline.convert.compress_audio"
        ) as mock_audio_compress:

            # Mock successful compression
            mock_video_compress.return_value = None
            mock_audio_compress.return_value = None

            # Process the HTML5 file with compression enabled
            with patch("ricecooker.config.COMPRESS", True):
                html_file = HTMLZipFile(temp_archive.name)
                result = html_file.process_file()

            # Verify both compression functions were called
            assert (
                mock_video_compress.called
            ), "Video compression should be called for MP4 files"
            assert (
                mock_audio_compress.called
            ), "Audio compression should be called for MP3 files"
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
            assert (
                mock_compress.called
            ), "Video compression should be called for WebM files"
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

        with patch(
            "ricecooker.utils.pipeline.convert.compress_video"
        ) as mock_video_compress, patch(
            "ricecooker.utils.pipeline.convert.compress_audio"
        ) as mock_audio_compress:

            # Process the HTML5 file with compression disabled
            with patch("ricecooker.config.COMPRESS", False):
                html_file = HTMLZipFile(temp_archive.name)
                result = html_file.process_file()

            # Verify compression functions were not called
            assert (
                not mock_video_compress.called
            ), "Video compression should not be called when disabled"
            assert (
                not mock_audio_compress.called
            ), "Audio compression should not be called when disabled"
            assert result is not None, "Processing should still succeed"

    finally:
        os.unlink(temp_archive.name)


# KPUB Conversion Tests
# These test the KPUBConversionHandler validation logic


def _create_kpub_archive(path, files_dict):
    """Helper to create a .kpub archive with given files."""
    with zipfile.ZipFile(path, "w") as zf:
        for filename, content in files_dict.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(filename, content)


def test_kpub_valid_archive_passes():
    """A valid KPUB with index.html should pass validation."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_archive.close()

    try:
        _create_kpub_archive(
            temp_archive.name,
            {"index.html": "<html><body><p>Hello world</p></body></html>"},
        )

        handler = KPUBConversionHandler()
        # Should not raise
        handler.validate_archive(temp_archive.name)
    finally:
        os.unlink(temp_archive.name)


def test_kpub_missing_index_html_fails():
    """A KPUB without index.html should fail validation."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_archive.close()

    try:
        _create_kpub_archive(
            temp_archive.name,
            {"content.html": "<html><body><p>Hello</p></body></html>"},
        )

        handler = KPUBConversionHandler()
        with pytest.raises(InvalidFileException) as exc_info:
            handler.validate_archive(temp_archive.name)

        assert "index.html" in str(exc_info.value).lower()
    finally:
        os.unlink(temp_archive.name)


def test_kpub_with_javascript_fails():
    """A KPUB containing .js files should fail validation."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_archive.close()

    try:
        _create_kpub_archive(
            temp_archive.name,
            {
                "index.html": "<html><body><p>Hello</p></body></html>",
                "script.js": "console.log('hello');",
            },
        )

        handler = KPUBConversionHandler()
        with pytest.raises(InvalidFileException) as exc_info:
            handler.validate_archive(temp_archive.name)

        error_msg = str(exc_info.value).lower()
        assert "javascript" in error_msg or ".js" in error_msg
    finally:
        os.unlink(temp_archive.name)


def test_kpub_with_css_file_fails():
    """A KPUB containing external .css files should fail validation."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_archive.close()

    try:
        _create_kpub_archive(
            temp_archive.name,
            {
                "index.html": "<html><body><p>Hello</p></body></html>",
                "styles.css": "body { color: red; }",
            },
        )

        handler = KPUBConversionHandler()
        with pytest.raises(InvalidFileException) as exc_info:
            handler.validate_archive(temp_archive.name)

        assert "css" in str(exc_info.value).lower()
    finally:
        os.unlink(temp_archive.name)


def test_kpub_with_inline_styles_passes():
    """A KPUB with inline styles (no external CSS) should pass validation."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_archive.close()

    try:
        _create_kpub_archive(
            temp_archive.name,
            {
                "index.html": '<html><body><p style="color: red;">Hello</p></body></html>'
            },
        )

        handler = KPUBConversionHandler()
        # Should not raise
        handler.validate_archive(temp_archive.name)
    finally:
        os.unlink(temp_archive.name)


def test_kpub_with_images_passes():
    """A KPUB with image files should pass validation."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_archive.close()

    try:
        # Create a minimal PNG (1x1 transparent pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        _create_kpub_archive(
            temp_archive.name,
            {
                "index.html": '<html><body><img src="image.png"></body></html>',
                "image.png": png_data,
            },
        )

        handler = KPUBConversionHandler()
        # Should not raise
        handler.validate_archive(temp_archive.name)
    finally:
        os.unlink(temp_archive.name)


def test_kpub_invalid_zip_fails():
    """A file with .kpub extension that isn't a valid zip should fail."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".kpub", delete=False)
    temp_file.write(b"not a zip file")
    temp_file.close()

    try:
        handler = KPUBConversionHandler()
        with pytest.raises(InvalidFileException) as exc_info:
            handler.validate_archive(temp_file.name)

        assert "zip" in str(exc_info.value).lower()
    finally:
        os.unlink(temp_file.name)
