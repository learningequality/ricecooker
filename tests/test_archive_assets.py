"""
Tests for ricecooker.utils.archive_assets — archive external reference processor.

Tests create in-memory ZIP archives, call download_and_rewrite_external_refs,
and verify the output directory contents. HTTP downloads are mocked.
"""

import json
import os
import shutil
import tempfile
import zipfile
from unittest.mock import patch

import pytest

from ricecooker.utils.archive_assets import download_and_rewrite_external_refs


class MockResponse:
    """Mock HTTP response for mocked downloads."""

    def __init__(self, content=b"downloaded content", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError

            raise HTTPError(response=self)


def _create_zip(files_dict):
    """Create a temporary ZIP file from a dict of {path: content}."""
    fd, zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path, content in files_dict.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(path, content)
    return zip_path


@pytest.fixture
def mock_download():
    """Mock make_request to return predictable content."""
    with patch("ricecooker.utils.archive_assets.make_request") as mock:
        mock.return_value = MockResponse(content=b"downloaded content")
        yield mock


@pytest.fixture
def mock_download_css_then_font():
    """Mock that returns CSS on first call and font bytes on subsequent calls."""
    css_content = b"@font-face { src: url('https://fonts.example.com/roboto.woff2') }"
    font_content = b"font-binary-data"

    responses = {
        "https://fonts.googleapis.com/css": MockResponse(content=css_content),
        "https://fonts.example.com/roboto.woff2": MockResponse(content=font_content),
    }

    def side_effect(url, *args, **kwargs):
        return responses.get(url, MockResponse(content=b"unknown", status_code=404))

    with patch("ricecooker.utils.archive_assets.make_request") as mock:
        mock.side_effect = side_effect
        yield mock


# ---------------------------------------------------------------------------
# Basic functionality tests
# ---------------------------------------------------------------------------


class TestBasicFunctionality:
    def test_html_with_external_img(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                # Image should be downloaded
                img_path = os.path.join(
                    result_dir, "_external", "cdn.example.com", "photo.jpg"
                )
                assert os.path.exists(img_path)

                # HTML should be rewritten
                with open(os.path.join(result_dir, "index.html")) as f:
                    html = f.read()
                assert "https://cdn.example.com/photo.jpg" not in html
                assert "_external/cdn.example.com/photo.jpg" in html

                mock_download.assert_called_once()
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_html_with_external_css(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css"></head></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                css_path = os.path.join(
                    result_dir, "_external", "fonts.googleapis.com", "css"
                )
                assert os.path.exists(css_path)

                with open(os.path.join(result_dir, "index.html")) as f:
                    html = f.read()
                assert "https://fonts.googleapis.com/css" not in html
                assert "_external/fonts.googleapis.com/css" in html
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_html_with_external_script(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><head><script src="https://cdn.example.com/lib.js"></script></head></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                js_path = os.path.join(
                    result_dir, "_external", "cdn.example.com", "lib.js"
                )
                assert os.path.exists(js_path)

                with open(os.path.join(result_dir, "index.html")) as f:
                    html = f.read()
                assert "_external/cdn.example.com/lib.js" in html
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_css_with_external_font(self, mock_download):
        zip_path = _create_zip(
            {
                "styles/main.css": "@font-face { src: url('https://fonts.example.com/roboto.woff2') format('woff2'); }"
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                font_path = os.path.join(
                    result_dir,
                    "_external",
                    "fonts.example.com",
                    "roboto.woff2",
                )
                assert os.path.exists(font_path)

                with open(os.path.join(result_dir, "styles", "main.css")) as f:
                    css = f.read()
                assert "https://fonts.example.com/roboto.woff2" not in css
                # Path should be relative from styles/ to _external/
                assert "../_external/fonts.example.com/roboto.woff2" in css
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_css_with_import(self, mock_download):
        zip_path = _create_zip(
            {
                "style.css": "@import 'https://fonts.googleapis.com/css?family=Roboto';"
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                css_path = os.path.join(
                    result_dir,
                    "_external",
                    "fonts.googleapis.com",
                    "css?family=Roboto",
                )
                assert os.path.exists(css_path)

                with open(os.path.join(result_dir, "style.css")) as f:
                    css = f.read()
                assert "https://fonts.googleapis.com" not in css
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_h5p_with_external_video(self, mock_download):
        content_json = json.dumps(
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
        zip_path = _create_zip(
            {
                "content/content.json": content_json,
                "h5p.json": '{"mainLibrary": "H5P.InteractiveVideo"}',
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                video_path = os.path.join(
                    result_dir,
                    "_external",
                    "h5p.org",
                    "sites",
                    "default",
                    "files",
                    "h5p",
                    "iv.mp4",
                )
                assert os.path.exists(video_path)

                with open(
                    os.path.join(result_dir, "content", "content.json")
                ) as f:
                    data = json.load(f)
                path_val = data["video"]["files"][0]["path"]
                assert "https://h5p.org" not in path_val
                assert "_external/" in path_val
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_relative_urls_unchanged(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="images/photo.jpg"></body></html>',
                "images/photo.jpg": b"fake-image-data",
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                with open(os.path.join(result_dir, "index.html")) as f:
                    html = f.read()
                assert 'src="images/photo.jpg"' in html
                mock_download.assert_not_called()
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_data_urls_unchanged(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="data:image/png;base64,abc123"></body></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                with open(os.path.join(result_dir, "index.html")) as f:
                    html = f.read()
                assert "data:image/png;base64,abc123" in html
                mock_download.assert_not_called()
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_download_failure_preserves_original(self):
        with patch("ricecooker.utils.archive_assets.make_request") as mock:
            mock.return_value = None  # Simulate failed download
            zip_path = _create_zip(
                {
                    "index.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>'
                }
            )
            try:
                result_dir = download_and_rewrite_external_refs(zip_path)
                try:
                    with open(os.path.join(result_dir, "index.html")) as f:
                        html = f.read()
                    # Original URL should be preserved when download fails
                    assert "https://cdn.example.com/photo.jpg" in html
                finally:
                    shutil.rmtree(result_dir, ignore_errors=True)
            finally:
                os.unlink(zip_path)

    def test_duplicate_urls_downloaded_once(self, mock_download):
        zip_path = _create_zip(
            {
                "page1.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>',
                "page2.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>',
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                # Download should only happen once for the same URL
                mock_download.assert_called_once()
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_css_recursive_download(self, mock_download_css_then_font):
        zip_path = _create_zip(
            {
                "index.html": '<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css"></head></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                # Both CSS and font should be downloaded
                css_path = os.path.join(
                    result_dir, "_external", "fonts.googleapis.com", "css"
                )
                font_path = os.path.join(
                    result_dir,
                    "_external",
                    "fonts.example.com",
                    "roboto.woff2",
                )
                assert os.path.exists(css_path)
                assert os.path.exists(font_path)

                # The downloaded CSS should have its font URL rewritten too
                with open(css_path) as f:
                    css = f.read()
                assert "https://fonts.example.com/roboto.woff2" not in css
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_empty_archive(self, mock_download):
        zip_path = _create_zip({"empty.txt": ""})
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                assert os.path.isdir(result_dir)
                mock_download.assert_not_called()
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_binary_files_untouched(self, mock_download):
        binary_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>',
                "images/local.png": binary_content,
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                with open(os.path.join(result_dir, "images", "local.png"), "rb") as f:
                    assert f.read() == binary_content
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_path_traversal_url_stays_in_temp_dir(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="https://evil.com/../../../etc/passwd"></body></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                # The downloaded file must be inside the result directory
                for root, _dirs, filenames in os.walk(result_dir):
                    for filename in filenames:
                        full_path = os.path.join(root, filename)
                        assert os.path.realpath(full_path).startswith(
                            os.path.realpath(result_dir)
                        ), f"File {full_path} escapes result directory"
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_blacklisted_urls_skipped(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": """<html><body>
                <img src="https://cdn.example.com/photo.jpg">
                <img src="https://blocked.example.com/img.jpg">
                </body></html>"""
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(
                zip_path, url_blacklist=["blocked.example.com"]
            )
            try:
                with open(os.path.join(result_dir, "index.html")) as f:
                    html = f.read()
                # Allowed URL should be downloaded and rewritten
                assert "_external/cdn.example.com/photo.jpg" in html
                # Blocked URL should remain unchanged
                assert "https://blocked.example.com/img.jpg" in html
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)


# ---------------------------------------------------------------------------
# Integration shape tests
# ---------------------------------------------------------------------------


class TestIntegrationShape:
    def test_returns_directory_path(self, mock_download):
        zip_path = _create_zip({"index.html": "<html><body></body></html>"})
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                assert os.path.isdir(result_dir)
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_original_files_preserved(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>',
                "images/local.png": b"png-data",
                "scripts/app.js": "console.log('hello');",
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                assert os.path.exists(os.path.join(result_dir, "index.html"))
                assert os.path.exists(
                    os.path.join(result_dir, "images", "local.png")
                )
                assert os.path.exists(
                    os.path.join(result_dir, "scripts", "app.js")
                )
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)

    def test_external_files_in_subdirectory(self, mock_download):
        zip_path = _create_zip(
            {
                "index.html": '<html><body><img src="https://cdn.example.com/photo.jpg"></body></html>'
            }
        )
        try:
            result_dir = download_and_rewrite_external_refs(zip_path)
            try:
                external_dir = os.path.join(result_dir, "_external")
                assert os.path.isdir(external_dir)
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
        finally:
            os.unlink(zip_path)
