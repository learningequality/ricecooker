"""Tests for audio and video compression in archive files."""

import json
import os
import tempfile
import zipfile
from unittest.mock import patch

from ricecooker import config
from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile


class MockResponse:
    """Mock HTTP response for archive asset downloads."""

    def __init__(self, content=b"downloaded content", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        pass


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


def test_html5_archive_external_refs_downloaded():
    """External URLs in HTML5 archives are downloaded and rewritten."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_archive.close()

    try:
        with zipfile.ZipFile(temp_archive.name, "w") as zf:
            zf.writestr(
                "index.html",
                '<html><body>Content here <img src="https://cdn.example.com/photo.jpg"></body></html>',
            )

        with patch("ricecooker.utils.archive_assets.make_request") as mock_request:
            mock_request.return_value = MockResponse(content=b"fake-image-data")

            with patch("ricecooker.config.COMPRESS", False):
                html_file = HTMLZipFile(temp_archive.name)
                result = html_file.process_file()

        assert result is not None, "Processing should succeed"

        # Verify the output ZIP contains the downloaded file and rewritten HTML
        result_path = config.get_storage_path(result)
        with zipfile.ZipFile(result_path, "r") as zf:
            names = zf.namelist()
            assert any(
                "_external/" in n for n in names
            ), f"Expected _external/ directory in output ZIP, got: {names}"

            html = zf.read("index.html").decode("utf-8")
            assert (
                "https://cdn.example.com/photo.jpg" not in html
            ), "External URL should be rewritten"
            assert "_external/" in html, "Should reference local _external/ path"

    finally:
        os.unlink(temp_archive.name)


def test_h5p_archive_external_video_downloaded():
    """External video URLs in H5P content.json are downloaded and rewritten."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".h5p", delete=False)
    temp_archive.close()

    content = json.dumps(
        {
            "video": {
                "files": [
                    {
                        "path": "https://h5p.org/sites/default/files/h5p/iv.mp4",
                        "mime": "video/mp4",
                    }
                ]
            }
        }
    )

    try:
        with zipfile.ZipFile(temp_archive.name, "w") as zf:
            zf.writestr("h5p.json", '{"mainLibrary": "H5P.InteractiveVideo"}')
            zf.writestr("content/content.json", content)

        with patch("ricecooker.utils.archive_assets.make_request") as mock_request:
            mock_request.return_value = MockResponse(content=b"fake-video-data")

            with patch("ricecooker.config.COMPRESS", False):
                h5p_file = H5PFile(temp_archive.name)
                result = h5p_file.process_file()

        assert result is not None, "Processing should succeed"

        result_path = config.get_storage_path(result)
        with zipfile.ZipFile(result_path, "r") as zf:
            names = zf.namelist()
            assert any(
                "_external/" in n for n in names
            ), f"Expected _external/ directory in output ZIP, got: {names}"

            data = json.loads(zf.read("content/content.json"))
            video_path = data["video"]["files"][0]["path"]
            assert (
                "https://h5p.org" not in video_path
            ), "External URL should be rewritten"
            assert "_external/" in video_path, "Should reference local path"

    finally:
        os.unlink(temp_archive.name)


def test_archive_external_refs_failure_graceful():
    """If external ref downloading fails, archive still processes successfully."""
    temp_archive = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_archive.close()

    try:
        with zipfile.ZipFile(temp_archive.name, "w") as zf:
            # Use unique content to avoid cache hit from previous test
            zf.writestr(
                "index.html",
                '<html><body>Unique failure test content <img src="https://cdn.example.com/photo.jpg"></body></html>',
            )

        with patch(
            "ricecooker.utils.pipeline.convert.download_and_rewrite_external_refs"
        ) as mock_process:
            mock_process.side_effect = OSError("Network error")

            with patch("ricecooker.config.COMPRESS", False):
                html_file = HTMLZipFile(temp_archive.name)
                result = html_file.process_file()

        assert (
            result is not None
        ), "Processing should succeed even on external ref failure"

        # Original URL should be preserved since processing failed
        result_path = config.get_storage_path(result)
        with zipfile.ZipFile(result_path, "r") as zf:
            html = zf.read("index.html").decode("utf-8")
            assert "https://cdn.example.com/photo.jpg" in html

    finally:
        os.unlink(temp_archive.name)
