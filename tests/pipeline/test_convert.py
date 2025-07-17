"""Tests for audio and video compression in archive files."""
import os
import tempfile
import zipfile
from unittest.mock import patch

from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile


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
