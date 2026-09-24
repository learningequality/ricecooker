"""Tests for audio and video compression in archive files."""

import base64
import json
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote
from urllib.parse import urljoin
from urllib.parse import urlsplit

import pytest
import requests
from bs4 import BeautifulSoup
from cachecontrol.caches.file_cache import FileCache
from le_utils.constants import content_kinds
from le_utils.constants import exercises
from le_utils.constants import format_presets
from le_utils.constants import licenses
from le_utils.constants import modalities
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import resource_type

from ricecooker import config
from ricecooker.classes.files import EPubFile
from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.exceptions import InvalidNodeException
from ricecooker.managers.tree import ChannelManager
from ricecooker.utils import archive_assets
from ricecooker.utils import caching
from ricecooker.utils.archive_dependencies import SharedAssetExtractor
from ricecooker.utils.imscp import IMSCPPackage
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.convert import BloomConversionHandler
from ricecooker.utils.pipeline.convert import DocumentConversionHandler
from ricecooker.utils.pipeline.convert import EPUBConversionHandler
from ricecooker.utils.pipeline.convert import H5PContentMapper
from ricecooker.utils.pipeline.convert import H5PConversionHandler
from ricecooker.utils.pipeline.convert import HTML5ConversionHandler
from ricecooker.utils.pipeline.convert import KPUBConversionHandler
from ricecooker.utils.pipeline.convert import PandocMissingError
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.references import CSSMapper
from ricecooker.utils.references import DEFAULT_MAPPERS
from ricecooker.utils.references import is_data_uri
from ricecooker.utils.references import is_external_url
from ricecooker.utils.references import mapper_for
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.zip import directory_member_names

# A valid 1x1 PNG, small enough to inline but real enough to pass the CONVERT
# stage's image verification (so external image refs survive download -> convert).
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_stub_output(input_path, output_path, **kwargs):
    """Stand in for compress_video/compress_audio: write a non-empty output.

    The conversion handlers write the compressed result through ``write_file``,
    which rejects an empty file, so a mocked compressor must produce some bytes.
    """
    with open(output_path, "wb") as fh:
        fh.write(b"compressed")


def test_html5_archive_with_mp4_compression(video_file, audio_file):
    """MP4 and MP3 files within HTML5 archives are compressed when settings are provided."""
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
            # The conversion handlers require the compressor to write a
            # non-empty output file, so fake that instead of a no-op.
            mock_video_compress.side_effect = _write_stub_output
            mock_audio_compress.side_effect = _write_stub_output

            # Compression settings flow through the pipeline's default context,
            # just as the chef supplies them for --compress.
            pipeline = FilePipeline(
                default_context={
                    "video_settings": {"crf": 32},
                    "audio_settings": {"bit_rate": 96},
                }
            )
            result = pipeline.execute(temp_archive.name, skip_cache=True)

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
    """WebM files within H5P archives are compressed when settings are provided."""
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
            # The conversion handler requires the compressor to write a
            # non-empty output file, so fake that instead of a no-op.
            mock_compress.side_effect = _write_stub_output

            # Compression settings flow through the pipeline's default context.
            pipeline = FilePipeline(default_context={"video_settings": {"crf": 32}})
            result = pipeline.execute(temp_archive.name, skip_cache=True)

            # Verify compression was called
            assert mock_compress.called, (
                "Video compression should be called for WebM files"
            )
            assert result is not None, "Processing should succeed"

    finally:
        os.unlink(temp_archive.name)


def test_archive_no_compression_without_settings(video_file, audio_file):
    """Archive media files are not compressed when no settings are provided."""
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
            # No compression settings in the default context.
            result = FilePipeline().execute(temp_archive.name, skip_cache=True)

            # Verify compression functions were not called
            assert not mock_video_compress.called, (
                "Video compression should not be called without settings"
            )
            assert not mock_audio_compress.called, (
                "Audio compression should not be called without settings"
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
                "dist/js/app.js": "console.log('hello');",
            }
        )
        # The common root is stripped, so index.html ends up at the root
        # and no entry point needs to be recorded.
        assert results[0].content_node_metadata is None
        with zipfile.ZipFile(results[0].path) as zf:
            names = set(zf.namelist())
        assert "index.html" in names
        assert "js/app.js" in names

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

    def test_non_index_entry_point_accepted(self):
        # Kolibri's KPUB renderer honours extra_fields.options.entry, so the
        # entry point need not be a root index.html.
        self._validate({"content.html": "<html><body><p>Hello</p></body></html>"})

    def test_no_html_file_rejected(self):
        with pytest.raises(InvalidFileException, match="(?i)no HTML file"):
            self._validate({"notes.txt": "no markup here"})

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


class TestKPUBSanitization:
    """Full-pipeline tests that KPUB CSS is sanitized in the produced archive."""

    @contextmanager
    def _run(self, index_html):
        """Build a KPUB, run the pipeline, yield the produced ``index.html`` text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.kpub")
            _create_archive(path, {"index.html": index_html})
            result = FilePipeline(default_context={}).execute(path, skip_cache=True)
            with zipfile.ZipFile(result[0].path) as zf:
                yield zf.read("index.html").decode("utf-8")

    def test_style_block_stripped(self):
        html = "<html><head><style>p{color:red}</style></head><body><p>Hi</p></body></html>"
        with self._run(html) as produced:
            assert "<style" not in produced

    def test_allowlisted_inline_style_survives(self):
        html = '<html><body><p style="text-align:center">Hi</p></body></html>'
        with self._run(html) as produced:
            assert "text-align" in produced

    def test_disallowed_inline_style_dropped(self):
        html = '<html><body><p style="position:absolute">Hi</p></body></html>'
        with self._run(html) as produced:
            assert "position" not in produced

    def test_mixed_inline_style_partial(self):
        html = '<html><body><p style="color:red;position:absolute">Hi</p></body></html>'
        with self._run(html) as produced:
            assert "color" in produced
            assert "position" not in produced

    def test_sanitizer_logs_removed(self, caplog):
        html = '<html><body><p style="position:absolute">Hi</p></body></html>'
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.kpub")
            _create_archive(path, {"index.html": html})
            with caplog.at_level("INFO"):
                result = FilePipeline(default_context={}).execute(path, skip_cache=True)
            assert result is not None
            assert any("position" in record.getMessage() for record in caplog.records)

    def test_stripped_refs_are_not_downloaded(self):
        # Sanitization runs before reference resolution, so a resource referenced
        # only from content the sanitizer removes — a url() inside a <style> block
        # or a dropped, non-allowlisted style= property — is never fetched, while a
        # legitimate <img src> still is.
        html = (
            "<html><head><style>body{background:url(https://ex.com/bg.png)}</style></head>"
            '<body><p style="background-image:url(https://ex.com/inline.png)">Hi</p>'
            '<img src="https://ex.com/keep.png"></body></html>'
        )
        url_to_content = {
            "https://ex.com/bg.png": _PNG_1x1,
            "https://ex.com/inline.png": _PNG_1x1,
            "https://ex.com/keep.png": _PNG_1x1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.kpub")
            _create_archive(path, {"index.html": html})
            with _fake_download_session(url_to_content) as fetched:
                FilePipeline(default_context={}).execute(path, skip_cache=True)
        assert "https://ex.com/keep.png" in fetched
        assert "https://ex.com/bg.png" not in fetched
        assert "https://ex.com/inline.png" not in fetched


def _make_source(tmpdir, ext, markdown):
    """Build a source document in ``ext`` from markdown (pandoc is a system dep)."""
    src = os.path.join(tmpdir, f"in.{ext}")
    if ext in ("md", "markdown"):
        with open(src, "w", encoding="utf-8") as f:
            f.write(markdown)
    else:
        subprocess.run(
            ["pandoc", "-f", "markdown", "-o", src],
            input=markdown,
            text=True,
            check=True,
        )
    return src


class TestDocumentConversion:
    """Document (docx/odt/rtf/md/markdown) -> KPUB conversion via pandoc."""

    @contextmanager
    def _convert(self, ext, markdown):
        """Convert a source doc through the pipeline, yield ``(result, ZipFile)``."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = _make_source(tmpdir, ext, markdown)
            result = FilePipeline(default_context={}).execute(src, skip_cache=True)
            with zipfile.ZipFile(result[0].path) as zf:
                yield result, zf

    @pytest.mark.parametrize("ext", ["docx", "odt", "rtf", "md", "markdown"])
    def test_each_format_converts_to_kpub(self, ext):
        with self._convert(ext, "# Title\n\nHello world") as (result, zf):
            assert result[0].preset == format_presets.KPUB_ZIP
            names = zf.namelist()
            assert "index.html" in names
            index = zf.read("index.html").decode("utf-8")
            body = BeautifulSoup(index, "lxml").find("body")
            assert body is not None
            assert body.get_text(strip=True)
            assert "<script" not in index
            assert "<style" not in index
            assert not any(n.lower().endswith((".js", ".css")) for n in names)

    def test_math_becomes_mathml(self):
        with self._convert("md", "# T\n\nInline $a^2+b^2$") as (_result, zf):
            index = zf.read("index.html").decode("utf-8")
            assert "<math" in index

    def test_images_land_under_media(self):
        data_uri = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode("ascii")
        markdown = f"# T\n\n![alt]({data_uri})"
        with self._convert("md", markdown) as (_result, zf):
            names = zf.namelist()
            assert any(n.startswith("media/") for n in names)
            index = zf.read("index.html").decode("utf-8")
            assert "media/" in index
            assert "data:image/png" not in index

    def test_pandoc_missing_raises(self):
        # The missing-pandoc guard raises before the source path is read, so no
        # real document is needed (building one would itself require pandoc).
        handler = DocumentConversionHandler()
        with patch("ricecooker.utils.pipeline.convert.shutil.which", return_value=None):
            with pytest.raises(PandocMissingError, match="(?i)install"):
                handler.handle_file("in.docx")


@contextmanager
def _fake_download_session(url_to_content):
    """Patch the pipeline's HTTP session so external refs resolve to fixed bytes.

    Only the network boundary is mocked; the real ``FilePipeline`` still runs each
    reference through download -> convert. An unmapped URL raises like a failed
    request, so tests exercise the leave-unrewritten path too. Yields the list of
    fetched URLs for call assertions.
    """
    calls = []

    def get(url, stream=True, timeout=None):
        calls.append(url)
        if url not in url_to_content:
            raise requests.exceptions.ConnectionError("no fake resource for " + url)
        content = url_to_content[url]
        return SimpleNamespace(
            headers={},
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size=8192: iter([content]),
        )

    def head(url, **kwargs):
        # The render handler HEAD-probes every external ref to see if it is an
        # HTML page; these fixtures are assets, so report a non-HTML type and let
        # the catch-all download handler fetch them via get().
        return SimpleNamespace(headers={"content-type": "application/octet-stream"})

    with patch.object(config, "DOWNLOAD_SESSION", SimpleNamespace(get=get, head=head)):
        yield calls


@contextmanager
def _run_external_refs(
    files, url_to_content, *, suffix=".zip", mappers=DEFAULT_MAPPERS
):
    """Build an archive from ``files``, run the processor, yield ``(dir, fetched)``.

    Extracts into a fresh temp dir (as ``handle_file`` does) and runs
    ``ArchiveProcessor`` over it with a real ``FilePipeline`` — only the download
    session is faked — so the test exercises the true download/convert paths.
    ``fetched`` is the list of URLs the pipeline requested.
    """
    pipeline = FilePipeline()
    convert_stage = next(c for c in pipeline._children if c.STAGE == "CONVERT")
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "in" + suffix)
        _create_archive(zip_path, files)
        out_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(out_dir)
        try:
            with _fake_download_session(url_to_content) as fetched:
                archive_assets.ArchiveProcessor(
                    out_dir, pipeline, convert_stage=convert_stage, mappers=mappers
                ).process()
            yield out_dir, fetched
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


class TestArchiveProcessor:
    """Archive-level external-resource downloading and reference rewriting."""

    def test_html(self):
        files = {
            "index.html": (
                "<html><head><title>Keep Me</title></head><body>"
                '<img src="https://ex.com/a.png">'
                '<script src="app.js"></script>'
                "</body></html>"
            ),
            "app.js": "console.log('hi');",
        }
        with _run_external_refs(files, {"https://ex.com/a.png": _PNG_1x1}) as (
            out_dir,
            _fetched,
        ):
            # The external asset was downloaded next to its referencing file.
            assets = [n for n in os.listdir(out_dir) if n.endswith(".png")]
            assert len(assets) == 1
            with open(os.path.join(out_dir, assets[0]), "rb") as f:
                assert f.read() == _PNG_1x1

            # The reference was rewritten to the local copy (its basename)...
            index = open(os.path.join(out_dir, "index.html")).read()
            assert "https://ex.com" not in index
            assert 'src="{}"'.format(assets[0]) in index

            # ...and the untouched structure survives surgical rewriting.
            soup = BeautifulSoup(index, "lxml")
            assert soup.find("title").string == "Keep Me"
            assert soup.find("script")["src"] == "app.js"

    def test_css_recursion(self):
        url_to_content = {
            "https://ex.com/fonts.css": b"@font-face{src:url(https://ex.com/f.woff2)}",
            "https://ex.com/f.woff2": b"WOFF2BYTES",
        }
        files = {
            "index.html": '<html><head><link rel="stylesheet" href="style.css"></head><body>x</body></html>',
            "style.css": "@import 'https://ex.com/fonts.css';",
        }
        with _run_external_refs(files, url_to_content) as (out_dir, _fetched):
            names = os.listdir(out_dir)
            # Both the imported CSS and the font it references were fetched.
            assert any(n.endswith(".css") and n != "style.css" for n in names)
            assert any(n.endswith(".woff2") for n in names)

            # The woff2 reference inside the downloaded CSS was rewritten.
            css_name = next(n for n in names if n.endswith(".css") and n != "style.css")
            downloaded_css = open(os.path.join(out_dir, css_name)).read()
            assert "https://ex.com/f.woff2" not in downloaded_css

    def test_h5p_json(self):
        files = {
            "h5p.json": '{"title": "x"}',
            "content/content.json": '{"video":{"files":[{"path":"https://h5p.org/iv.png","mime":"image/png"}]}}',
        }
        with _run_external_refs(
            files,
            {"https://h5p.org/iv.png": _PNG_1x1},
            suffix=".h5p",
            mappers=(H5PContentMapper(),),
        ) as (out_dir, _fetched):
            content = json.load(open(os.path.join(out_dir, "content", "content.json")))
            new_path = content["video"]["files"][0]["path"]
            assert new_path != "https://h5p.org/iv.png"
            # The asset lives inside content/ and the rewritten path is
            # content-relative (no ../), the only form H5P.getPath resolves.
            assert not new_path.startswith("../")
            resolved = os.path.normpath(os.path.join(out_dir, "content", new_path))
            assert os.path.exists(resolved)

    def test_data_uri_exploded(self):
        """A ``data:`` URI is localized: decoded to a real file, ref rewritten.

        Runs the real ``FilePipeline`` — ``Base64FileHandler`` decodes the URI,
        so no network is needed.
        """
        data_uri = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()
        files = {
            "index.html": '<html><body><img src="{}"></body></html>'.format(data_uri),
        }
        with _run_external_refs(files, {}) as (out_dir, _fetched):
            pngs = [n for n in os.listdir(out_dir) if n.endswith(".png")]
            assert len(pngs) == 1
            index = open(os.path.join(out_dir, "index.html")).read()
            assert "data:image/png" not in index
            assert 'src="{}"'.format(pngs[0]) in index

    def test_leaves_internal_refs(self):
        files = {
            "index.html": '<html><body><img src="images/local.png"></body></html>',
            "images/local.png": b"LOCAL",
        }
        with _run_external_refs(files, {}) as (out_dir, fetched):
            # No download was attempted for the relative reference.
            assert fetched == []
            index = open(os.path.join(out_dir, "index.html")).read()
            assert 'src="images/local.png"' in index


def _zipcontent_target(zip_name, member, ref):
    """``(zip, member)`` Kolibri's zipcontent serves for ``ref`` in ``member`` of ``zip_name``, else None."""
    parts = urlsplit(urljoin(f"/zipcontent/{zip_name}/{member}", ref)).path.split(
        "/", 3
    )
    if len(parts) < 4 or parts[1] != "zipcontent":
        return None
    return parts[2], unquote(parts[3])


def _as_bytes(files):
    return {
        name: content.encode("utf-8") if isinstance(content, str) else content
        for name, content in files.items()
    }


def _write_tree(directory, files):
    for member, content in _as_bytes(files).items():
        path = os.path.join(directory, member)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)


def _read_tree(directory):
    """``{member: bytes}`` for every file under ``directory``."""
    tree = {}
    for name in directory_member_names(directory):
        with open(os.path.join(directory, name), "rb") as fh:
            tree[name] = fh.read()
    return tree


def _refs(directory, member):
    """The references ``member`` of ``directory`` makes, in order."""
    with open(os.path.join(directory, member), encoding="utf-8") as fh:
        content = fh.read()
    return mapper_for(member).extract(content)


def _tempdir_is_case_insensitive():
    with tempfile.TemporaryDirectory() as tmp:
        probe = os.path.join(tmp, "probe")
        open(probe, "wb").close()
        return os.path.exists(os.path.join(tmp, "PROBE"))


# These fixtures hold paths differing only in case, which collide on macOS and Windows.
_needs_case_sensitive_fs = pytest.mark.skipif(
    _tempdir_is_case_insensitive(),
    reason="temp dir is case-insensitive",
)


@contextmanager
def _shared_extraction(files, leaves, outside=None):
    """Extract what ``leaves`` (key -> members, entry first) of a package of ``files`` share into ``dep.zip``.

    Yields ``(leaf_dirs, dep, rewritten)``: each leaf dir holds the members the
    leaf keeps, and ``dep`` is the dependency dir as ``{member: bytes}``.
    ``outside`` files are written beside the package.
    """
    with tempfile.TemporaryDirectory() as tmp:
        _write_tree(tmp, outside or {})
        package = IMSCPPackage(os.path.join(tmp, "package"))
        _write_tree(package.directory, files)
        closures = {key: package.closure(members) for key, members in leaves.items()}
        extractor = SharedAssetExtractor(
            package, {key: (closures[key], leaves[key][0]) for key in leaves}
        )
        dep_dir = os.path.join(tmp, "dep")
        os.makedirs(dep_dir)
        selected = extractor.select(dep_dir)
        leaf_dirs = {key: os.path.join(tmp, "leaves", key) for key in leaves}
        rewritten = set()
        for key, closure in closures.items():
            paths = {m: m for m in closure if m not in extractor.shared(key)}
            package.copy(paths, leaf_dirs[key])
            if selected and extractor.rewrite(key, leaf_dirs[key], paths, "dep.zip"):
                rewritten.add(key)
        yield leaf_dirs, _read_tree(dep_dir), rewritten


class TestSharedAssetExtractor:
    def test_css_referencing_unshared_image_stays(self):
        files = {}
        for key, bg in (("a", b"A"), ("b", b"B")):
            files[f"{key}/index.html"] = (
                '<link rel="stylesheet" href="site.css"><script src="../lib/x.js"></script>'
            )
            files[f"{key}/site.css"] = "body{background:url(bg.png)}"
            files[f"{key}/bg.png"] = bg
        files["lib/x.js"] = "X"
        leaves = {"a": ["a/index.html"], "b": ["b/index.html"]}
        with _shared_extraction(files, leaves) as (leaf_dirs, dep, _rewritten):
            assert list(dep) == ["lib/x.js"]
            for key, directory in leaf_dirs.items():
                tree = _read_tree(directory)
                for member in (f"{key}/site.css", f"{key}/bg.png"):
                    assert tree[member] == _as_bytes(files)[member]

    def test_css_stays_when_copies_reference_different_bytes(self):
        specs = {"a": ("x", b"A"), "b": ("y", b"B"), "c": ("x", b"A"), "d": ("y", b"B")}
        files = {}
        for key, (folder, bg) in specs.items():
            files[f"{key}/index.html"] = (
                f'<link rel="stylesheet" href="{folder}/site.css">'
            )
            files[f"{key}/{folder}/site.css"] = "body{background:url(bg.png)}"
            files[f"{key}/{folder}/bg.png"] = bg
        leaves = {key: [f"{key}/index.html"] for key in specs}
        with _shared_extraction(files, leaves) as (leaf_dirs, dep, _rewritten):
            assert sorted(dep) == ["a/x/bg.png", "b/y/bg.png"]
            for key, (folder, bg) in specs.items():
                css = f"{key}/{folder}/site.css"
                assert os.path.exists(os.path.join(leaf_dirs[key], css))
                (ref,) = _refs(leaf_dirs[key], css)
                zip_name, member = _zipcontent_target("leaf.zip", css, ref)
                assert zip_name == "dep.zip"
                assert dep[member] == bg

    def test_moved_css_points_at_canonical_copy(self):
        page = '<link rel="stylesheet" href="../s/site.css"><img src="../p/bg.png">'
        files = {
            "a/index.html": page,
            "b/index.html": page,
            "s/site.css": "body{background:url(../q/bg.png)}",
            "p/bg.png": _PNG_1x1,
            "q/bg.png": _PNG_1x1,
        }
        leaves = {"a": ["a/index.html"], "b": ["b/index.html"]}
        with _shared_extraction(files, leaves) as (_dirs, dep, _rewritten):
            assert sorted(dep) == ["p/bg.png", "s/site.css"]
            (ref,) = CSSMapper().extract(dep["s/site.css"].decode("utf-8"))
            assert posixpath.normpath(posixpath.join("s", ref)) == "p/bg.png"

    def test_rewritten_ref_keeps_encoding_query_and_fragment(self):
        page = '<img src="../img/my%20pic.png?v=2#top">'
        files = {"a/index.html": page, "b/index.html": page, "img/my pic.png": _PNG_1x1}
        leaves = {"a": ["a/index.html"], "b": ["b/index.html"]}
        with _shared_extraction(files, leaves) as (leaf_dirs, _dep, _rw):
            (ref,) = _refs(leaf_dirs["a"], "a/index.html")
            parts = urlsplit(ref)
            assert (parts.query, parts.fragment) == ("v=2", "top")
            assert _zipcontent_target("leaf.zip", "a/index.html", ref) == (
                "dep.zip",
                "img/my pic.png",
            )

    def test_reference_escaping_the_package_is_ignored(self):
        files = {
            "a/index.html": '<link rel="stylesheet" href="../site.css">',
            "b/index.html": '<link rel="stylesheet" href="../site.css">',
            "site.css": "body{background:url(../evil.png)}",
        }
        leaves = {"a": ["a/index.html"], "b": ["b/index.html"]}
        with _shared_extraction(files, leaves, {"evil.png": b"EVIL"}) as (
            leaf_dirs,
            dep,
            _rewritten,
        ):
            assert dep == {}
            evil = os.path.join(
                os.path.dirname(os.path.dirname(leaf_dirs["a"])), "evil.png"
            )
            with open(evil, "rb") as fh:
                assert fh.read() == b"EVIL"
            for key, directory in leaf_dirs.items():
                members = [f"{key}/index.html", "site.css"]
                assert _read_tree(directory) == {
                    m: _as_bytes(files)[m] for m in members
                }

    @_needs_case_sensitive_fs
    def test_paths_differing_in_case_stay_apart(self):
        files = {"img/h.png": b"X", "IMG/h.png": b"Y"}
        for key, folder in (("a", "img"), ("b", "IMG"), ("c", "img"), ("d", "IMG")):
            files[f"{key}/index.html"] = f'<img src="../{folder}/h.png">'
        leaves = {key: [f"{key}/index.html"] for key in "abcd"}
        with _shared_extraction(files, leaves) as (leaf_dirs, dep, rewritten):
            assert dep == {"img/h.png": b"X"}
            for key in ("b", "d"):
                assert _read_tree(leaf_dirs[key])["IMG/h.png"] == b"Y"
            assert rewritten == {"a", "c"}

    @_needs_case_sensitive_fs
    def test_file_and_directory_at_one_path_stay_apart(self):
        files = {"lib": b"X", "LIB/h.png": b"Y"}
        for key, ref in (
            ("a", "lib"),
            ("b", "LIB/h.png"),
            ("c", "lib"),
            ("d", "LIB/h.png"),
        ):
            files[f"{key}/index.html"] = f'<img src="../{ref}">'
        leaves = {key: [f"{key}/index.html"] for key in "abcd"}
        with _shared_extraction(files, leaves) as (leaf_dirs, dep, rewritten):
            assert dep == {"lib": b"X"}
            for key in ("b", "d"):
                assert _read_tree(leaf_dirs[key])["LIB/h.png"] == b"Y"
            assert rewritten == {"a", "c"}

    def test_html_pages_never_move(self):
        frameset = '<frameset><frame src="../nav.html"></frameset>'
        files = {
            "a/index.html": frameset,
            "b/index.html": frameset,
            "nav.html": '<a href="p.html">P</a>',
            "p.html": "<p>P</p>",
        }
        leaves = {key: [f"{key}/index.html", "nav.html", "p.html"] for key in "ab"}
        with _shared_extraction(files, leaves) as (leaf_dirs, dep, _rw):
            assert dep == {}
            for directory in leaf_dirs.values():
                assert {"nav.html", "p.html"} <= set(_read_tree(directory))

    def test_leaf_with_non_utf8_page_sits_out(self):
        files = {
            "a/index.html": '<script src="../lib/x.js"></script>',
            "b/index.html": '<script src="../lib/x.js"></script>',
            "b/p2.html": "caf\xe9".encode("latin-1"),
            "lib/x.js": "X",
        }
        leaves = {"a": ["a/index.html"], "b": ["b/index.html", "b/p2.html"]}
        with _shared_extraction(files, leaves) as (leaf_dirs, dep, _rewritten):
            assert dep == {}
            members = ["b/index.html", "b/p2.html", "lib/x.js"]
            assert _read_tree(leaf_dirs["b"]) == {
                m: _as_bytes(files)[m] for m in members
            }


class TestH5PContentMapper:
    """H5P ``content.json`` ``path`` extraction/rewriting.

    All H5P knowledge lives with the H5P handler, so its mapper is tested here
    rather than against the generic reference library. Every string value stored
    under a ``"path"`` key anywhere in the parsed JSON is a resource reference;
    non-``path`` strings are left alone even when they equal a mapped value.
    """

    CONTENT_JSON = (
        '{"video":{"files":['
        '{"path":"https://h5p.org/iv.mp4","mime":"video/mp4"},'
        '{"path":"images/local.png"}'
        "]}}"
    )

    def test_handles_only_content_json(self):
        mapper = H5PContentMapper()
        assert mapper.handles("content/content.json")
        assert not mapper.handles("h5p.json")
        assert not mapper.handles("content/other.json")

    def test_extract(self):
        mapper = H5PContentMapper()
        assert mapper.extract(self.CONTENT_JSON) == [
            "https://h5p.org/iv.mp4",
            "images/local.png",
        ]
        # Sanity check the fixture parses.
        assert json.loads(self.CONTENT_JSON)

    def test_rewrite(self):
        mapper = H5PContentMapper()
        rewritten = mapper.rewrite(
            self.CONTENT_JSON, {"https://h5p.org/iv.mp4": "_static/iv.mp4"}
        )
        files = json.loads(rewritten)["video"]["files"]
        assert files[0]["path"] == "_static/iv.mp4"
        # The local path was not mapped, so it is left unchanged.
        assert files[1]["path"] == "images/local.png"

    def test_rewrite_only_touches_path_keys(self):
        mapper = H5PContentMapper()
        # A non-"path" string that happens to equal a mapped value stays intact.
        content = '{"path":"a.mp4","label":"a.mp4"}'
        data = json.loads(mapper.rewrite(content, {"a.mp4": "_static/a.mp4"}))
        assert data["path"] == "_static/a.mp4"
        assert data["label"] == "a.mp4"


class TestHandlerExternalRefIntegration:
    """Task 6: conversion handlers opt into external-ref downloading before zipping."""

    def _process(self, file_cls, files, suffix):
        temp_archive = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_archive.close()
        try:
            _create_archive(temp_archive.name, files)
            return file_cls(temp_archive.name).process_file()
        finally:
            os.unlink(temp_archive.name)

    def test_html5_handler_downloads_external_refs(self):
        html = {"index.html": "<html><body><p>hi</p></body></html>"}
        with patch("ricecooker.utils.archive_assets.ArchiveProcessor") as spy:
            self._process(HTMLZipFile, html, ".zip")
        assert spy.call_count == 1
        _, kwargs = spy.call_args
        # The HTML5 handler passes the generic web mappers (HTML + CSS) and no
        # H5P mapper.
        assert kwargs["mappers"] == HTML5ConversionHandler.REFERENCE_MAPPERS
        assert not any(isinstance(m, H5PContentMapper) for m in kwargs["mappers"])

    def test_h5p_handler_scans_content_json(self):
        files = {
            "h5p.json": '{"title": "x"}',
            "content/content.json": '{"a": 1}',
        }
        with patch("ricecooker.utils.archive_assets.ArchiveProcessor") as spy:
            self._process(H5PFile, files, ".h5p")
        assert spy.call_count == 1
        _, kwargs = spy.call_args
        # The H5P handler adds an H5PContentMapper on top of the web defaults.
        assert kwargs["mappers"] == H5PConversionHandler.REFERENCE_MAPPERS
        assert any(isinstance(m, H5PContentMapper) for m in kwargs["mappers"])

    def test_epub_handler_scans_external_refs(self):
        # Every archive format now scans HTML/CSS for external refs, EPUB
        # included; the processor fires with the generic web mappers.
        files = {
            "mimetype": "application/epub+zip",
            "META-INF/container.xml": (
                '<?xml version="1.0"?>'
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="content.opf" '
                'media-type="application/oebps-package+xml"/></rootfiles></container>'
            ),
            "content.opf": (
                '<?xml version="1.0"?>'
                '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
                '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                "<dc:title>x</dc:title></metadata>"
                '<manifest><item id="c" href="c.html" media-type="application/xhtml+xml"/></manifest>'
                '<spine><itemref idref="c"/></spine></package>'
            ),
            "c.html": "<html><body><p>hi</p></body></html>",
        }
        with patch("ricecooker.utils.archive_assets.ArchiveProcessor") as spy:
            self._process(EPubFile, files, ".epub")
        assert spy.call_count == 1
        _, kwargs = spy.call_args
        assert kwargs["mappers"] == EPUBConversionHandler.REFERENCE_MAPPERS

    def test_all_archive_handlers_declare_web_mappers(self):
        # Every archive format scans HTML/CSS; only H5P adds a format-specific
        # mapper on top.
        for handler_cls in (
            HTML5ConversionHandler,
            EPUBConversionHandler,
            KPUBConversionHandler,
            BloomConversionHandler,
        ):
            names = {type(m).__name__ for m in handler_cls.REFERENCE_MAPPERS}
            assert {"HTMLMapper", "CSSMapper"} <= names
            assert "H5PContentMapper" not in names
        assert any(
            isinstance(m, H5PContentMapper)
            for m in H5PConversionHandler.REFERENCE_MAPPERS
        )

    def test_html5_end_to_end_downloads_and_rewrites(self):
        files = {
            "index.html": '<html><body><img src="https://ex.com/a.png"></body></html>',
        }
        # Drive the whole HTMLZipFile.process_file path; only the download session
        # is faked, so the handler downloads and rewrites through its real pipeline.
        with _fake_download_session({"https://ex.com/a.png": _PNG_1x1}):
            filename = self._process(HTMLZipFile, files, ".zip")

        # The produced archive contains the downloaded asset (next to index.html)
        # and a rewritten reference.
        with zipfile.ZipFile(config.get_storage_path(filename)) as zf:
            names = zf.namelist()
            assert any(n.endswith(".png") for n in names)
            index = zf.read("index.html").decode("utf-8")
            assert "https://ex.com" not in index


class TestKPUBPromotion:
    """A static-article HTML5 zip is promoted to a KPUB; interactive stays HTML5."""

    def _run(self, files, context=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.zip")
            _create_archive(path, files)
            return FilePipeline(default_context={}).execute(
                path, context=context, skip_cache=True
            )

    @pytest.mark.parametrize("via_file", [True, False])
    def test_legacy_html5_apis_keep_static_zip_html5(self, via_file):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.zip")
            _create_archive(
                path, {"index.html": "<html><body><p>An article</p></body></html>"}
            )
            source = {"files": [HTMLZipFile(path)]} if via_file else {"uri": path}
            node = HTML5AppNode(
                source_id="static",
                title="Static",
                license=get_license("CC BY", copyright_holder="Holder"),
                pipeline=FilePipeline(),
                **source,
            )
            node.process_files()
        assert [f.get_preset() for f in node.files] == [format_presets.HTML5_ZIP]

    def test_static_article_promoted_to_kpub(self):
        result = self._run(
            {
                "index.html": "<html><body><p>An article</p><img src='a.png'></body></html>"
            }
        )
        assert result[0].preset == format_presets.KPUB_ZIP
        assert result[0].filename.endswith(".kpub")
        assert result[0].content_node_metadata["kind"] == content_kinds.DOCUMENT

    def test_interactive_zip_stays_html5(self):
        result = self._run(
            {
                "index.html": "<html><body><p>App</p><script src='app.js'></script></body></html>",
                "app.js": "console.log('interactive');",
            }
        )
        assert result[0].preset == format_presets.HTML5_ZIP
        assert result[0].content_node_metadata["kind"] == content_kinds.HTML5

    @pytest.mark.parametrize(
        "files",
        [
            {
                "index.html": "<html><body><p>App</p><script>go();</script></body></html>"
            },
            # A content function sharing an LMS API name is not plumbing.
            {
                "index.html": "<html><body><button onclick='Initialize()'>Go</button>"
                "<script>function Initialize(){alert(1);}</script></body></html>"
            },
            # Neither is content code alongside an LMS call.
            {
                "index.html": "<html><body><p id='x'>SCO</p><script>LMSInitialize('');"
                "document.getElementById('x').innerHTML='Hi';</script></body></html>"
            },
            # Any page's script counts, not just the entry's.
            {
                "index.html": "<html><body><a href='p2.html'>Next</a></body></html>",
                "p2.html": "<html><body><script>go();</script></body></html>",
            },
        ],
    )
    def test_content_scripts_stay_html5(self, files):
        result = self._run(files)
        assert result[0].preset == format_presets.HTML5_ZIP

    def test_non_utf8_page_stays_html5_unaltered(self):
        index = (
            "<html><head><meta charset='iso-8859-1'></head>"
            "<body><p>Educación</p></body></html>"
        ).encode("latin-1")
        result = self._run({"index.html": index})
        assert result[0].preset == format_presets.HTML5_ZIP
        with zipfile.ZipFile(result[0].path) as zf:
            assert zf.read("index.html") == index

    def test_inline_lms_plumbing_stripped_and_promoted(self):
        result = self._run(
            {
                "index.html": "<html><body><p>Static SCO</p>"
                "<script>LMSInitialize('');</script></body></html>"
            }
        )
        assert result[0].preset == format_presets.KPUB_ZIP

    def test_scorm_boilerplate_stripped_and_promoted(self):
        # A static SCO whose only script is a SCORM wrapper: the plumbing carries
        # no content, so it is stripped and the page becomes a KPUB.
        result = self._run(
            {
                "index.html": (
                    "<html><body><p>Static SCO</p>"
                    "<script src='SCORM_API_wrapper.js'></script></body></html>"
                ),
                "SCORM_API_wrapper.js": "function LMSInitialize(){}",
            }
        )
        assert result[0].preset == format_presets.KPUB_ZIP
        with zipfile.ZipFile(result[0].path) as zf:
            assert zf.namelist() == ["index.html"]

    def test_css_member_stripped_and_promoted(self):
        # Unnecessary styling is not a reason to ship a whole HTML5 zip.
        result = self._run(
            {
                "index.html": (
                    "<html><head><link rel='stylesheet' href='style.css'></head>"
                    "<body><p>Styled</p></body></html>"
                ),
                "style.css": "p{color:red}",
            }
        )
        assert result[0].preset == format_presets.KPUB_ZIP
        with zipfile.ZipFile(result[0].path) as zf:
            assert zf.namelist() == ["index.html"]
            assert "style.css" not in zf.read("index.html").decode("utf-8")

    def test_downloaded_external_css_stripped_on_promotion(self):
        # Promotion is judged after reference resolution, so a stylesheet that was
        # downloaded into the archive is stripped rather than sealed into a .kpub.
        with _fake_download_session({"https://ex.com/s.css": b"p{color:red}"}):
            result = self._run(
                {
                    "index.html": (
                        "<html><head>"
                        "<link rel='stylesheet' href='https://ex.com/s.css'>"
                        "</head><body><p>Prose</p></body></html>"
                    )
                }
            )
        assert result[0].preset == format_presets.KPUB_ZIP
        with zipfile.ZipFile(result[0].path) as zf:
            assert not any(n.endswith(".css") for n in zf.namelist())

    def test_non_index_entry_promoted_with_entry_hint(self):
        # A KPUB may name its entry point, so a static article at another path is
        # promoted and the entry recorded for the renderer.
        result = self._run({"article.html": "<html><body><p>Prose</p></body></html>"})
        assert result[0].preset == format_presets.KPUB_ZIP
        assert result[0].content_node_metadata["extra_fields"] == {
            "options": {"entry": "article.html"}
        }


_IMSCP_FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "testcontent", "imscp"
)


def _tree_dict_leaves(node):
    """Yield the content-leaf dicts (kind + files) of a decomposed tree dict."""
    children = node.get("children")
    if children is not None:
        for child in children:
            yield from _tree_dict_leaves(child)
    elif node.get("kind"):
        yield node


def _build_single_resource_imscp(
    path,
    href,
    index_html,
    extra_files=None,
    item_xml="",
    root="",
):
    """Write a minimal one-resource IMSCP package.

    ``item_xml`` is spliced inside the ``<item>`` (per-item LOM, a masteryscore).
    ``root`` wraps the whole package in a folder.
    """
    files = {unquote(href): index_html}
    file_entries = '<file href="{}"/>'.format(href)
    for name, content in (extra_files or {}).items():
        files[name] = content
        file_entries += '<file href="{}"/>'.format(name)
    files["imsmanifest.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
        'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2" identifier="MAN">'
        '<organizations default="ORG">'
        '<organization identifier="ORG"><title>Org</title>'
        '<item identifier="ITEM" identifierref="RES"><title>Leaf</title>'
        "{}</item>"
        "</organization></organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="{}">'
        "{}</resource></resources>"
        "</manifest>"
    ).format(item_xml, href, file_entries)
    _create_archive(path, {root + name: content for name, content in files.items()})


_QTI3 = "http://www.imsglobal.org/xsd/imsqtiasi_v3p0"


def _qti_item(identifier, body="", head=""):
    return (
        f'<qti-assessment-item xmlns="{_QTI3}" identifier="{identifier}" title="{identifier}" '
        'adaptive="false" time-dependent="false">'
        '<qti-response-declaration identifier="RESPONSE" cardinality="single" base-type="identifier">'
        "<qti-correct-response><qti-value>A</qti-value></qti-correct-response>"
        f"</qti-response-declaration>{head}<qti-item-body>{body}"
        '<qti-choice-interaction response-identifier="RESPONSE" max-choices="1">'
        '<qti-simple-choice identifier="A">A</qti-simple-choice></qti-choice-interaction>'
        '</qti-item-body><qti-response-processing template="https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/match_correct"/>'
        "</qti-assessment-item>"
    )


def _qti_refs(*hrefs, tag="qti-assessment-item-ref"):
    return "".join(
        f'<{tag} identifier="ref{i}" href="{href}"/>' for i, href in enumerate(hrefs)
    )


def _qti_test(identifier, refs_xml):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<qti-assessment-test xmlns="{_QTI3}" identifier="{identifier}" title="{identifier}">'
        '<qti-test-part identifier="P" navigation-mode="linear" submission-mode="individual">'
        f'<qti-assessment-section identifier="S" title="S" visible="true">{refs_xml}'
        "</qti-assessment-section></qti-test-part></qti-assessment-test>"
    )


_QTI2_ITEM = (
    '<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="old" '
    'title="old" adaptive="false" timeDependent="false"/>'
)


@contextmanager
def _qti_package(resources, files):
    """Zip ``files`` under a QTI manifest of ``(identifier, type, href)`` resources."""
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsglobal.org/xsd/qti/qtiv3p0/imscp_v1p1" '
        'identifier="MAN"><organizations/><resources>{}</resources></manifest>'
    ).format(
        "".join(
            f'<resource identifier="{identifier}" type="{type_}" href="{href}">'
            f'<file href="{href}"/></resource>'
            for identifier, type_, href in resources
        )
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "package.zip")
        _create_archive(path, {"imsmanifest.xml": manifest, **files})
        yield path


_ARTICLE_HTML = "<html><body><h1>Title</h1><p>Prose.</p></body></html>"

# Per-item LOM covering every mapped section: general, educational, rights and
# lifeCycle contributors.
_LOM_ITEM_XML = (
    "<metadata><lom>"
    "<general><keyword><langstring>databases</langstring></keyword>"
    "<description><langstring>A short article.</langstring></description>"
    "</general>"
    "<educational><learningResourceType><value>"
    "<langstring>narrative text</langstring></value></learningResourceType>"
    "</educational>"
    "<rights><description><langstring>"
    "Creative Commons Attribution-ShareAlike 4.0"
    "</langstring></description></rights>"
    "<lifeCycle><contribute><role><value><langstring>author</langstring>"
    "</value></role><entity>FN:Ada Lovelace</entity></contribute>"
    "{}</lifeCycle>"
    "</lom></metadata>"
)
_CONTENT_PROVIDER_XML = (
    "<contribute><role><value><langstring>content provider</langstring>"
    "</value></role><entity>ORG:Analytical Press</entity></contribute>"
)


def _build_imscp(path, resources, files):
    """Write a package of ``files`` with one item per ``(identifier, href, extra hrefs)`` resource."""
    items = "".join(
        '<item identifier="ITEM_{0}" identifierref="{0}"><title>{0}</title></item>'.format(
            identifier
        )
        for identifier, _href, _extra in resources
    )
    declared = "".join(
        '<resource identifier="{}" type="webcontent" href="{}">{}</resource>'.format(
            identifier,
            href,
            "".join('<file href="{}"/>'.format(h) for h in [href, *extra]),
        )
        for identifier, href, extra in resources
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="MAN">'
        '<organizations default="ORG"><organization identifier="ORG"><title>Org</title>'
        "{}</organization></organizations><resources>{}</resources></manifest>"
    ).format(items, declared)
    _create_archive(path, {**files, "imsmanifest.xml": manifest})


def _zip_refs(path):
    """``(member, ref)`` for every local reference a mapped member of the zip at ``path`` makes."""
    with zipfile.ZipFile(path) as zf:
        for member in zf.namelist():
            mapper = mapper_for(member)
            if mapper is None:
                continue
            for ref in mapper.extract(zf.read(member).decode("utf-8")):
                if is_external_url(ref) or is_data_uri(ref) or not urlsplit(ref).path:
                    continue
                yield member, ref


def _unresolved_references(zips):
    """``(zip, member, ref)`` for each ref in ``zips`` ({filename: path}) zipcontent can't serve from them."""
    namelists = {}
    for name, path in zips.items():
        with zipfile.ZipFile(path) as zf:
            namelists[name] = set(zf.namelist())
    unresolved = []
    for name, path in zips.items():
        for member, ref in _zip_refs(path):
            target = _zipcontent_target(name, member, ref)
            if target is None or target[1] not in namelists.get(target[0], ()):
                unresolved.append((name, member, ref))
    return unresolved


def _reachable(zips, zip_name, member):
    """``(zip, member)`` pairs zipcontent serves by following refs from ``member`` of ``zip_name``."""
    refs = {name: defaultdict(list) for name in zips}
    for name, path in zips.items():
        for source, ref in _zip_refs(path):
            refs[name][source].append(ref)
    seen = set()
    pending = [(zip_name, member)]
    while pending:
        name, source = pending.pop()
        for ref in refs.get(name, {}).get(source, ()):
            target = _zipcontent_target(name, source, ref)
            if target is not None and target not in seen:
                seen.add(target)
                pending.append(target)
    return seen


def _page(body, head=""):
    return f"<html><head>{head}</head><body>{body}</body></html>"


_SCO1 = ("SCO1", "sco1/index.html", ["sco1/private.png", "sco1/unused.txt"])
_SCO2 = ("SCO2", "sco2/pages/page.html", ["sco2/unused.txt"])
_SCO3 = ("SCO3", "sco3/index.html", ["sco3/app.js"])
_STATIC = ("STATIC", "static/article.html", [])
_SHARED_RESOURCES = [_SCO1, _SCO2, _STATIC]
_SHARED_FILES = {
    "sco1/index.html": _page(
        '<p>One.</p><img src="private.png">',
        '<link rel="stylesheet" href="../css/site.css"><script src="../lib/jquery.js"></script>',
    ),
    "sco1/private.png": b"PRIVATE",
    "sco1/unused.txt": "unused",
    "sco2/pages/page.html": _page(
        "<p>Two.</p>",
        '<link rel="stylesheet" href="../../css/site.css"><script src="../../lib2/jquery.js"></script>',
    ),
    "sco2/unused.txt": "unused",
    "sco3/index.html": _page("<p>Three.</p>", '<script src="app.js"></script>'),
    "sco3/app.js": "/* app */",
    "static/article.html": _page(
        '<h1>Static</h1><p>Prose.</p><img src="../img/bg.png">'
    ),
    "css/site.css": "body{background:url(../img/bg.png)}",
    "img/bg.png": _PNG_1x1,
    "lib/jquery.js": "/* jquery */",
    "lib2/jquery.js": "/* jquery */",
}


def _decompose_package(resources, files, pipeline=None, downloads=None, context=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "package.zip")
        _build_imscp(path, resources, files)
        # skip_cache doesn't reach the per-leaf runs, so give them a fresh cache.
        cache = FileCache(os.path.join(tmp, "cache"), forever=True)
        with (
            _fake_download_session(downloads or {}),
            patch.object(caching, "FILECACHE", cache),
        ):
            result = (pipeline or FilePipeline()).execute(
                path, context=context, skip_cache=True
            )
    return result[0].content_node_metadata


def _leaves_by_title(tree):
    return {leaf["title"]: leaf for leaf in _tree_dict_leaves(tree)}


def _filenames(leaf):
    return {f["filename"] for f in leaf["files"]}


def _primary_file(leaf):
    """The file dict of the zip ``leaf`` is sealed into."""
    (primary,) = [
        f for f in leaf["files"] if f["preset"] != format_presets.HTML5_DEPENDENCY_ZIP
    ]
    return primary


def _primary_members(leaf):
    return _zip_members(_primary_file(leaf)["path"])


def _tree_files(tree):
    return [f for leaf in _tree_dict_leaves(tree) for f in leaf["files"]]


def _tree_zips(tree):
    """``{filename: storage path}`` of every file ``tree``'s leaves carry."""
    return {f["filename"]: f["path"] for f in _tree_files(tree)}


def _dependency_filenames(tree):
    return {
        f["filename"]
        for f in _tree_files(tree)
        if f["preset"] == format_presets.HTML5_DEPENDENCY_ZIP
    }


def _dependency_filename(tree):
    """The one dependency zip ``tree``'s leaves share."""
    filenames = _dependency_filenames(tree)
    assert len(filenames) == 1, filenames
    return filenames.pop()


def _zip_members(path):
    with zipfile.ZipFile(path) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


_VIDEO_FILES = {
    "v1/index.html": _page(
        '<p>v1</p><video src="../media/clip.mp4"></video><video src="own.mp4"></video>',
        '<script src="../lib/jquery.js"></script>',
    ),
    "v2/index.html": _page(
        '<p>v2</p><video src="../media/clip.mp4"></video>',
        '<script src="../lib/jquery.js"></script>',
    ),
    "v1/own.mp4": b"OWN",
    "media/clip.mp4": b"CLIP",
    "lib/jquery.js": "/* jquery */",
}
_VIDEO_RESOURCES = [
    ("V1", "v1/index.html", ["v1/own.mp4"]),
    ("V2", "v2/index.html", []),
]


def _expanded_node(chef_license, copyright_holder=True, item_xml=None):
    """Expand a one-article LOM package through ContentNode, which becomes the article."""
    if item_xml is None:
        item_xml = _LOM_ITEM_XML.format(
            _CONTENT_PROVIDER_XML if copyright_holder else ""
        )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "meta.zip")
        _build_single_resource_imscp(
            path, "article.html", _ARTICLE_HTML, item_xml=item_xml
        )
        node = ContentNode(
            source_id="pkg",
            title="Pkg",
            license=chef_license,
            uri=path,
            pipeline=FilePipeline(),
        )
        node.process_files()
    return node


class TestIMSCPDecomposition:
    """The IMSCP handler decomposes a package into a native node subtree."""

    def _run(self, zip_name):
        path = os.path.join(_IMSCP_FIXTURE_DIR, zip_name)
        # Any external reference inside a resource fails gracefully (left
        # unrewritten) instead of hitting the network, keeping the test hermetic.
        with _fake_download_session({}):
            result = FilePipeline().execute(path, skip_cache=True)
        return result[0].content_node_metadata

    def _decompose(self, *args, **kwargs):
        """Decompose a synthetic one-resource package and return its tree."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "package.zip")
            _build_single_resource_imscp(path, *args, **kwargs)
            return (
                FilePipeline().execute(path, skip_cache=True)[0].content_node_metadata
            )

    def _decompose_items(self, items_xml, resources):
        """Decompose a package of ``items_xml`` over ``{identifier: href}`` article
        resources (``.xml`` hrefs are QTI) and return its tree."""
        files = {
            "imsmanifest.xml": (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
                'identifier="MAN"><organizations default="ORG">'
                '<organization identifier="ORG">{}</organization></organizations>'
                "<resources>{}</resources></manifest>"
            ).format(
                items_xml,
                "".join(
                    '<resource identifier="{}" type="{}" href="{}">'
                    '<file href="{}"/></resource>'.format(
                        identifier,
                        "imsqti_xmlv1p2" if href.endswith(".xml") else "webcontent",
                        href,
                        href,
                    )
                    for identifier, href in resources.items()
                ),
            )
        }
        files.update({href: _ARTICLE_HTML for href in resources.values()})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "package.zip")
            _create_archive(path, files)
            return (
                FilePipeline().execute(path, skip_cache=True)[0].content_node_metadata
            )

    def test_hot_potatoes_package_rejected(self):
        # test_quiz is a Hot Potatoes JQuiz SCO: its only leaf is rejected, so the
        # package fails rather than becoming an empty topic.
        with pytest.raises(InvalidFileException, match="every resource was rejected"):
            self._run("test_quiz.zip")

    @pytest.mark.parametrize(
        "index_html,item_xml",
        [
            # A mastery score on the item means the resource is graded.
            (_ARTICLE_HTML, "<adlcp:masteryscore>80</adlcp:masteryscore>"),
            # So does writing a score, even though doing so goes through the LMS
            # API calls that are otherwise discounted as plumbing.
            (
                "<html><body><p>Task</p>"
                '<script>LMSSetValue("cmi.core.score.raw", 80);</script></body></html>',
                "",
            ),
        ],
    )
    def test_assessment_resource_rejected(self, index_html, item_xml):
        with pytest.raises(InvalidFileException, match="every resource was rejected"):
            self._decompose("page.html", index_html, item_xml=item_xml)

    def test_rejected_package_node_carries_pipeline_error(self):
        with pytest.raises(InvalidNodeException, match="every resource was rejected"):
            _expanded_node(
                get_license(licenses.PUBLIC_DOMAIN),
                item_xml="<adlcp:masteryscore>80</adlcp:masteryscore>",
            )

    def test_gitta_has_multiple_html5_leaves(self):
        tree = self._run("gitta_ims.zip")
        leaves = list(_tree_dict_leaves(tree))
        assert len(leaves) > 1
        assert all(leaf["kind"] == content_kinds.HTML5 for leaf in leaves)
        assert all(leaf["title"].strip() for leaf in leaves)
        # Topic items carry pages of their own (the unit introductions).
        assert "Definition of Terms" in {leaf["title"] for leaf in leaves}

        # gitta's resources declare no <file> members at all and their entry
        # points sit deep in the package, so a leaf sealed from the manifest
        # alone would be an unstyled orphan page. The assets each entry
        # references are staged with it, and every leaf shares the templates.
        dependency = _dependency_filename(tree)
        assert all(dependency in _filenames(leaf) for leaf in leaves)
        zips = _tree_zips(tree)
        assert _unresolved_references(zips) == []

        entry = (
            leaves[0].get("extra_fields", {}).get("options", {}).get("entry")
            or "index.html"
        )
        assert entry in _primary_members(leaves[0])
        leaf_zip = _primary_file(leaves[0])["filename"]
        reached = {member for _zip, member in _reachable(zips, leaf_zip, entry)}
        assert any(m.endswith(".css") for m in reached)
        assert any(m.endswith((".gif", ".png", ".jpg")) for m in reached)

    def test_wrapped_media_becomes_a_media_node(self, video_file):
        with open(video_file.path, "rb") as fh:
            mp4 = fh.read()
        tree = self._decompose(
            "page.html",
            "<html><body><video src='clip.mp4'></video></body></html>",
            {"clip.mp4": mp4},
        )
        leaves = list(_tree_dict_leaves(tree))
        assert len(leaves) == 1
        assert leaves[0]["kind"] == content_kinds.VIDEO
        assert any(f["filename"].endswith(".mp4") for f in leaves[0]["files"])

    @pytest.mark.parametrize(
        "index_html",
        [
            "<html><body><h1>Title</h1><p>Prose here.</p>"
            "<img src='pic.png'></body></html>",
            # Kolibri has no image content kind, so a page wrapping a single
            # picture stays the article it already is rather than collapsing to a
            # media node that could not exist.
            "<html><body><img src='pic.png'></body></html>",
        ],
    )
    def test_static_article_becomes_kpub(self, index_html):
        tree = self._decompose("article.html", index_html, {"pic.png": _PNG_1x1})
        leaves = list(_tree_dict_leaves(tree))
        assert len(leaves) == 1
        assert leaves[0]["kind"] == content_kinds.DOCUMENT
        assert any(f["preset"] == format_presets.KPUB_ZIP for f in leaves[0]["files"])

    def test_lom_metadata_lands_on_the_expanded_node(self):
        # Through the real consumer: LOM general/educational/rights/lifeCycle
        # metadata maps onto the decomposed leaf's own content-node fields, and its
        # license (with the copyright holder LOM names) overrides the chef's.
        leaf = _expanded_node(get_license("CC BY", copyright_holder="Pkg holder"))
        # A lone resource needs no folder: the declared node becomes it.
        assert leaf.kind == content_kinds.DOCUMENT
        assert leaf.children == []
        assert leaf.source_id == "pkg"
        assert leaf.license.license_id == licenses.CC_BY_SA
        assert leaf.license.copyright_holder == "Analytical Press"
        assert leaf.learning_activities == [learning_activities.READ]
        assert leaf.resource_types == [resource_type.TEXTBOOK]
        assert leaf.tags == ["databases"]
        assert leaf.author == "Ada Lovelace"
        assert leaf.description == "A short article."

    def test_inferred_license_needing_a_holder_is_ignored(self):
        # The LOM names CC BY-SA but nobody to attribute it to. Applying it would
        # fail node validation and abort the whole channel, so the chef's license
        # is kept instead.
        leaf = _expanded_node(
            get_license(licenses.PUBLIC_DOMAIN), copyright_holder=False
        )
        assert leaf.kind == content_kinds.DOCUMENT
        assert leaf.license.license_id == licenses.PUBLIC_DOMAIN

    def test_manifest_href_traversal_is_rejected(self):
        # A manifest whose href points outside the extracted package (a hostile
        # ../ traversal) must not read that file into the decomposed output: the
        # resource is dropped, leaving nothing to decompose.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "evil.zip")
            manifest = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
                'identifier="MAN">'
                '<organizations default="ORG">'
                '<organization identifier="ORG"><title>Org</title>'
                '<item identifier="ITEM" identifierref="RES"><title>Leaf</title></item>'
                "</organization></organizations>"
                '<resources><resource identifier="RES" type="webcontent" '
                'href="../../../../../../../../etc/passwd"></resource></resources>'
                "</manifest>"
            )
            _create_archive(path, {"imsmanifest.xml": manifest})
            with pytest.raises(
                InvalidFileException, match="every resource was rejected"
            ):
                FilePipeline().execute(path, skip_cache=True)

    @pytest.mark.parametrize("href", ["sco/intro.html", "sco/intro.htm"])
    def test_nested_index_is_the_entry(self, href):
        tree = self._decompose(
            href,
            _ARTICLE_HTML,
            {"sco/p2.html": _ARTICLE_HTML, "shared/pic.png": _PNG_1x1},
        )
        (leaf,) = _tree_dict_leaves(tree)
        assert leaf["extra_fields"]["options"]["entry"] == href

    def test_uri_encoded_href_resolves(self):
        tree = self._decompose("my%20page.html", _ARTICLE_HTML)
        assert len(list(_tree_dict_leaves(tree))) == 1

    def test_package_in_wrapping_folder_decomposes(self):
        tree = self._decompose("page.html", _ARTICLE_HTML, root="course/")
        assert len(list(_tree_dict_leaves(tree))) == 1

    def test_multilingual_title_is_one_string(self):
        tree = self._decompose_items(
            "<item identifier='A' identifierref='R1'><metadata><lom><general><title>"
            "<langstring xml:lang='en'>English</langstring>"
            "<langstring xml:lang='fr'>Français</langstring>"
            "</title></general></lom></metadata></item>",
            {"R1": "a.html"},
        )
        (leaf,) = tree["children"]
        assert leaf["title"] == "English"

    def test_nested_resources_collapse_into_one_folder(self):
        # Single-child wrappers (organization, A, B) and a folder left with one
        # resource after a rejection (C) are all collapsed away; a folder left
        # with none (D) is dropped.
        tree = self._decompose_items(
            "<item identifier='A'><title>A</title>"
            "<item identifier='B'><title>B</title>"
            "<item identifier='P1' identifierref='R1'><title>P1</title></item>"
            "<item identifier='C'><title>C</title>"
            "<item identifier='P2' identifierref='R2'><title>P2</title></item>"
            "<item identifier='Q' identifierref='QTI'><title>Q</title></item>"
            "</item>"
            "<item identifier='D'><title>D</title>"
            "<item identifier='Q2' identifierref='QTI'><title>Q2</title></item>"
            "</item></item></item>",
            {"R1": "p1.html", "R2": "p2.html", "QTI": "q.xml"},
        )
        assert [child["title"] for child in tree["children"]] == ["P1", "P2"]
        assert all(
            child["kind"] == content_kinds.DOCUMENT for child in tree["children"]
        )

    def test_ims_md_metadata_lands_on_the_expanded_node(self):
        # IMS MD 1.2 (SCORM 1.2) lowercases element names, capitalises
        # vocabulary terms, and wraps contributors' vCards in <centity>.
        leaf = _expanded_node(
            get_license("CC BY", copyright_holder="Pkg holder"),
            item_xml="<metadata><lom>"
            "<educational><learningresourcetype><value>"
            "<langstring>Narrative Text</langstring></value></learningresourcetype>"
            "</educational>"
            "<lifecycle><contribute><role><value><langstring>Author</langstring>"
            "</value></role><centity><vcard>BEGIN:VCARD VERSION:3.0 "
            "FN:Ada Lovelace N:Lovelace;Ada END:VCARD</vcard></centity>"
            "</contribute></lifecycle>"
            "</lom></metadata>",
        )
        assert leaf.learning_activities == [learning_activities.READ]
        assert leaf.author == "Ada Lovelace"

    def test_rights_description_keeps_the_inherited_holder(self):
        leaf = _expanded_node(
            get_license("CC BY", copyright_holder="Pkg holder"),
            item_xml="<metadata><lom><rights><description>"
            "<langstring>Some rights text</langstring>"
            "</description></rights></lom></metadata>",
        )
        assert leaf.license.copyright_holder == "Pkg holder"

    def test_packages_sharing_identifiers_expand_distinctly(self):
        manifest = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
            'identifier="MAN"><organizations default="ORG">'
            '<organization identifier="ORG"><title>Org</title>'
            "<item identifier='ITEMA' identifierref='RA'><title>A</title></item>"
            "<item identifier='ITEMB' identifierref='RB'><title>B</title></item>"
            "</organization></organizations><resources>"
            '<resource identifier="RA" type="webcontent" href="a.html">'
            '<file href="a.html"/></resource>'
            '<resource identifier="RB" type="webcontent" href="b.html">'
            '<file href="b.html"/></resource>'
            "</resources></manifest>"
        )
        channel = ChannelNode("channel", "example.org", "Channel")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "package.zip")
            _create_archive(
                path,
                {
                    "imsmanifest.xml": manifest,
                    "a.html": _ARTICLE_HTML,
                    "b.html": _ARTICLE_HTML,
                },
            )
            for source_id in ("math-course", "history-course"):
                node = ContentNode(
                    source_id=source_id,
                    title=source_id,
                    license=get_license("CC BY", copyright_holder="Holder"),
                    uri=path,
                    pipeline=FilePipeline(),
                )
                channel.add_child(node)
                node.process_files()
        # The chef's title wins over the organization's.
        assert [node.title for node in channel.children] == [
            "math-course",
            "history-course",
        ]
        leaves = [leaf for node in channel.children for leaf in node.children]
        assert len(leaves) == 4
        assert len({leaf.get_content_id() for leaf in leaves}) == 4

    def test_legacy_html5_apis_keep_the_package_whole(self):
        path = os.path.join(_IMSCP_FIXTURE_DIR, "eventos.zip")
        node = HTML5AppNode(
            source_id="eventos",
            title="Eventos",
            license=get_license("CC BY", copyright_holder="ESSI"),
            files=[HTMLZipFile(path)],
        )
        with _fake_download_session({}):
            node.process_files()
        assert node.kind == content_kinds.HTML5
        assert node.children == []
        with zipfile.ZipFile(config.get_storage_path(node.files[0].filename)) as zf:
            # Processed as an HTML5 zip rather than uploaded raw.
            assert "imsmanifest.xml" in zf.namelist()
        node.validate()

    def test_end_to_end_node_expansion(self):
        # A ContentNode whose uri is an IMSCP package expands into a TOPIC subtree
        # of processed leaves, whose files are queued for upload.
        path = os.path.join(_IMSCP_FIXTURE_DIR, "eventos.zip")
        node = ContentNode(
            source_id="eventos",
            title="Eventos",
            license=get_license("CC BY", copyright_holder="ESSI"),
            uri=path,
            pipeline=FilePipeline(),
        )
        channel = ChannelNode("eventos-channel", "example.org", "Channel")
        channel.add_child(node)
        with _fake_download_session({}):
            files_to_upload = ChannelManager(channel).process_tree()
        assert node.kind == content_kinds.TOPIC
        assert node.files == []
        # The single organization and its root item are collapsed into the node.
        assert (
            node.children[0].title == "Evento's Solutions, servicios integrales (ESSI)"
        )
        topics = [node]
        for topic in topics:
            topics += [c for c in topic.children if c.kind == content_kinds.TOPIC]
        assert all(len(topic.children) != 1 for topic in topics)

        leaves = node.get_non_topic_descendants()
        assert leaves
        assert all(leaf.kind == content_kinds.HTML5 for leaf in leaves)
        # eXe's residual jQuery/effects and .js/.css members keep pages off KPUB,
        # and those shared assets ship once, in a dependency zip every leaf carries.
        presets = {format_presets.HTML5_ZIP, format_presets.HTML5_DEPENDENCY_ZIP}
        assert all({f.get_preset() for f in leaf.files} == presets for leaf in leaves)
        files = [f for leaf in leaves for f in leaf.files]
        # Each leaf is backed by its own sealed zip, not the shared package.
        filenames = {preset: [] for preset in presets}
        for f in files:
            filenames[f.get_preset()].append(f.get_filename())
        leaf_filenames = filenames[format_presets.HTML5_ZIP]
        assert len(leaf_filenames) == len(set(leaf_filenames))
        assert len(set(filenames[format_presets.HTML5_DEPENDENCY_ZIP])) == 1
        assert {f.get_filename() for f in files} <= set(files_to_upload)

    def test_shared_assets_move_to_one_dependency_zip(self):
        tree = _decompose_package(_SHARED_RESOURCES, _SHARED_FILES)
        leaves = _leaves_by_title(tree)
        dependency = _dependency_filename(tree)
        assert dependency in _filenames(leaves["SCO1"])
        assert dependency in _filenames(leaves["SCO2"])
        assert dependency not in _filenames(leaves["STATIC"])
        assert sorted(_zip_members(_tree_zips(tree)[dependency])) == [
            "css/site.css",
            "img/bg.png",
            "lib/jquery.js",
        ]
        sco1 = _primary_members(leaves["SCO1"])
        assert "unused.txt" in sco1 and "private.png" in sco1
        assert "unused.txt" in _primary_members(leaves["SCO2"])

    def test_every_reference_resolves_through_zipcontent(self):
        tree = _decompose_package(_SHARED_RESOURCES, _SHARED_FILES)
        zips = _tree_zips(tree)
        assert _unresolved_references(zips) == []
        dependency = _dependency_filename(tree)
        leaves = _leaves_by_title(tree)
        for title in ("SCO1", "SCO2"):
            leaf_zip = _primary_file(leaves[title])
            assert any(
                _zipcontent_target(leaf_zip["filename"], member, ref)[0] == dependency
                for member, ref in _zip_refs(leaf_zip["path"])
            )

    def test_kpub_leaf_keeps_its_assets(self):
        tree = _decompose_package(_SHARED_RESOURCES, _SHARED_FILES)
        kpub = _primary_file(_leaves_by_title(tree)["STATIC"])
        assert "img/bg.png" in _zip_members(kpub["path"])
        alone = _decompose_package([_STATIC], _SHARED_FILES)
        alone_kpub = _primary_file(_leaves_by_title(alone)["STATIC"])
        assert alone_kpub["filename"] == kpub["filename"]

    @pytest.mark.parametrize("resources", [[_SCO1], [_SCO1, _SCO3]])
    def test_no_dependency_zip_without_sharing(self, resources):
        tree = _decompose_package(resources, _SHARED_FILES)
        assert _dependency_filenames(tree) == set()
        sco1 = _primary_members(_leaves_by_title(tree)["SCO1"])
        assert {"lib/jquery.js", "css/site.css", "img/bg.png"} <= set(sco1)

    def test_shared_media_staged_once(self):
        with tempfile.TemporaryDirectory() as root:
            copies = []

            def counting_zip(path, *args, **kwargs):
                tree = _read_tree(root)
                copies.append(sum(content == b"CLIP" for content in tree.values()))
                return create_predictable_zip(path, *args, **kwargs)

            with (
                patch.object(tempfile, "tempdir", root),
                patch(
                    "ricecooker.utils.pipeline.convert.create_predictable_zip",
                    side_effect=counting_zip,
                ),
            ):
                tree = _decompose_package(_VIDEO_RESOURCES, _VIDEO_FILES)
        assert _dependency_filename(tree)
        # The extracted package's copy, plus the dependency dir's until it seals.
        assert max(copies) == 2

    def test_package_compression_settings_reach_every_leaf(self):
        def stub(input_path, output_path, **kwargs):
            with open(input_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read() + b"|crf=%d" % kwargs["crf"])

        context = {"video_settings": {"crf": 32}}
        with patch(
            "ricecooker.utils.pipeline.convert.compress_video", side_effect=stub
        ):
            tree = _decompose_package(_VIDEO_RESOURCES, _VIDEO_FILES, context=context)
        dependency = _zip_members(_tree_zips(tree)[_dependency_filename(tree)])
        assert dependency["media/clip.mp4"] == b"CLIP|crf=32"
        v1 = _primary_members(_leaves_by_title(tree)["V1"])
        assert v1["own.mp4"] == b"OWN|crf=32"

    def test_wrapped_media_gets_package_compression_settings(self, video_file):
        with open(video_file.path, "rb") as fh:
            mp4 = fh.read()
        files = {
            "m/page.html": _page("<video src='clip.mp4'></video>"),
            "m/clip.mp4": mp4,
        }
        context = {"video_settings": {"crf": 40}}
        tree = _decompose_package(
            [("MEDIA", "m/page.html", ["m/clip.mp4"])], files, context=context
        )
        (leaf,) = _tree_dict_leaves(tree)
        (expected,) = [
            f.filename
            for f in FilePipeline().execute(
                video_file.path, context=context, skip_cache=True
            )
        ]
        assert _filenames(leaf) == {expected}

    def test_downloaded_cdn_asset_is_shared(self):
        url = "https://cdn.example.org/lib.js"
        files = {
            f"{folder}/index.html": _page(
                f"<p>{folder}</p>", f'<script src="{url}"></script>'
            )
            for folder in ("cdn1", "cdn2")
        }
        resources = [("CDN1", "cdn1/index.html", []), ("CDN2", "cdn2/index.html", [])]
        tree = _decompose_package(resources, files, downloads={url: b"lib"})
        dependency = _dependency_filename(tree)
        zips = _tree_zips(tree)
        assert list(_zip_members(zips[dependency]).values()) == [b"lib"]
        for leaf in _tree_dict_leaves(tree):
            assert b"lib" not in _primary_members(leaf).values()
        assert _unresolved_references(zips) == []

    def test_shared_media_compression_failure_keeps_other_leaves(self):
        pipeline = FilePipeline(default_context={"video_settings": {"crf": 32}})
        files = {**_VIDEO_FILES, **_SHARED_FILES}
        # ffmpeg can't compress the fixture's placeholder bytes.
        tree = _decompose_package([*_VIDEO_RESOURCES, _SCO3], files, pipeline)
        assert list(_leaves_by_title(tree)) == ["SCO3"]
        assert _dependency_filenames(tree) == set()


_QTI_TEST = "imsqti_test_xmlv3p0"
_QTI_ITEM = "imsqti_item_xmlv3p0"
_QTI_QUIZ_FIELDS = {
    "mastery_model": exercises.DO_ALL,
    "randomize": False,
    "options": {"modality": modalities.QUIZ},
}


class TestQTIIngestion:
    def _ingest(self, resources, files):
        with _qti_package(resources, files) as path:
            return (
                FilePipeline().execute(path, skip_cache=True)[0].content_node_metadata
            )

    @staticmethod
    def _ids(leaf):
        return [q["id"] for q in leaf["questions"]]

    def test_each_test_becomes_an_exercise_in_test_order(self):
        tree = self._ingest(
            [
                ("T1", _QTI_TEST, "tests/t.xml"),
                ("T2", _QTI_TEST, "t2.xml"),
                ("A", _QTI_ITEM, "items/a.xml"),
                ("B", _QTI_ITEM, "items/b.xml"),
            ],
            {
                "tests/t.xml": _qti_test(
                    "t", _qti_refs("../items/b.xml", "../items/a.xml")
                ),
                "t2.xml": _qti_test("t2", _qti_refs("items/a.xml")),
                "items/a.xml": _qti_item("a"),
                "items/b.xml": _qti_item("b"),
            },
        )
        leaves = tree["children"]
        assert [leaf["title"] for leaf in leaves] == ["t", "t2"]
        assert all(leaf["kind"] == content_kinds.EXERCISE for leaf in leaves)
        assert [self._ids(leaf) for leaf in leaves] == [["b", "a"], ["a"]]
        assert all(leaf["extra_fields"] == _QTI_QUIZ_FIELDS for leaf in leaves)

    def test_loose_items_become_one_exercise(self):
        tree = self._ingest(
            [("A", _QTI_ITEM, "a.xml"), ("B", _QTI_ITEM, "b.xml")],
            {"a.xml": _qti_item("a"), "b.xml": _qti_item("b")},
        )
        (leaf,) = tree["children"]
        assert self._ids(leaf) == ["a", "b"]

    def test_item_byte_order_mark_is_dropped(self):
        tree = self._ingest(
            [("A", _QTI_ITEM, "a.xml")],
            {
                "a.xml": b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>'
                + _qti_item("a").encode("utf-8")
            },
        )
        (leaf,) = tree["children"]
        (question,) = leaf["questions"]
        assert question["raw_data"] == _qti_item("a")

    def test_section_refs_are_followed_once(self):
        section = (
            f'<qti-assessment-section xmlns="{_QTI3}" identifier="s" title="s" visible="true">'
            f"{_qti_refs('../items/b.xml')}"
            f"{_qti_refs('s.xml', tag='qti-assessment-section-ref')}"
            "</qti-assessment-section>"
        )
        tree = self._ingest(
            [("T", _QTI_TEST, "t.xml")],
            {
                "t.xml": _qti_test(
                    "t",
                    _qti_refs("items/a.xml")
                    + _qti_refs("sections/s.xml", tag="qti-assessment-section-ref"),
                ),
                "sections/s.xml": section,
                "items/a.xml": _qti_item("a"),
                "items/b.xml": _qti_item("b"),
            },
        )
        (leaf,) = tree["children"]
        assert self._ids(leaf) == ["a", "b"]

    def test_non_qti3_items_are_rejected_by_name(self, caplog):
        tree = self._ingest(
            [
                ("A", _QTI_ITEM, "a.xml"),
                ("OLD", "imsqti_item_xmlv2p1", "items/old.xml"),
            ],
            {"a.xml": _qti_item("a"), "items/old.xml": _QTI2_ITEM},
        )
        (leaf,) = tree["children"]
        assert self._ids(leaf) == ["a"]
        assert any(
            "items/old.xml" in r.getMessage() and "QTI 3.0" in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.parametrize("resource_type", ["imsqti_item_xmlv2p1", "imsqti_xmlv1p2"])
    def test_pre_qti3_only_package_is_rejected(self, resource_type):
        with pytest.raises(InvalidFileException, match="every resource was rejected"):
            self._ingest(
                [("OLD", resource_type, "items/old.xml")],
                {"items/old.xml": _QTI2_ITEM},
            )

    def test_repeated_item_ids_are_kept_once(self):
        tree = self._ingest(
            [("T", _QTI_TEST, "t.xml")],
            {
                "t.xml": _qti_test(
                    "t",
                    _qti_refs(
                        "items/a.xml", "items/a.xml", "items/copy.xml", "items/b.xml"
                    ),
                ),
                "items/a.xml": _qti_item("a"),
                "items/copy.xml": _qti_item("a"),
                "items/b.xml": _qti_item("b"),
            },
        )
        (leaf,) = tree["children"]
        assert self._ids(leaf) == ["a", "b"]

    def test_item_images_are_stored_and_rewritten(self):
        items = {
            "items/a.xml": _qti_item(
                "a", '<img src="../images/pic.png" srcset="../images/pic.png 2x"/>'
            ),
            "items/b.xml": _qti_item(
                "b", '<object data="../images/pic.png" type="image/png"/>'
            ),
        }
        tree = self._ingest(
            [("A", _QTI_ITEM, "items/a.xml"), ("B", _QTI_ITEM, "items/b.xml")],
            {**items, "images/pic.png": _PNG_1x1},
        )
        (leaf,) = tree["children"]
        filenames = set()
        for question, original in zip(leaf["questions"], items.values()):
            assert [f["preset"] for f in question["files"]] == [
                format_presets.EXERCISE_IMAGE
            ]
            filename = question["files"][0]["filename"]
            assert re.match(r"^[0-9a-f]{32}\.png$", filename)
            assert os.path.isfile(config.get_storage_path(filename))
            assert question["raw_data"] == original.replace(
                "../images/pic.png", filename
            )
            filenames.add(filename)
        assert len(filenames) == 1

    @pytest.mark.parametrize(
        "body",
        [
            '<audio src="../media/a.mp3"/>',
            '<img src="../images/missing.png"/>',
            '<img src="../../../../etc/x.png"/>',
        ],
    )
    def test_items_with_unusable_media_are_rejected(self, caplog, body):
        tree = self._ingest(
            [("OK", _QTI_ITEM, "items/ok.xml"), ("BAD", _QTI_ITEM, "items/bad.xml")],
            {
                "items/ok.xml": _qti_item("ok"),
                "items/bad.xml": _qti_item("bad", body),
                "media/a.mp3": b"ID3",
            },
        )
        (leaf,) = tree["children"]
        assert self._ids(leaf) == ["ok"]
        assert any("items/bad.xml" in r.getMessage() for r in caplog.records)

    def test_item_stylesheets_are_stripped(self):
        stylesheets = (
            '<qti-stylesheet href="../css/style.css" type="text/css"/>'
            '<qti-stylesheet href="https://example.org/s.css" type="text/css"></qti-stylesheet>'
        )
        tree = self._ingest(
            [("A", _QTI_ITEM, "items/a.xml")],
            {"items/a.xml": _qti_item("a", head=stylesheets), "css/style.css": "p {}"},
        )
        (leaf,) = tree["children"]
        (question,) = leaf["questions"]
        assert question["raw_data"] == _qti_item("a")
        assert question["files"] == []

    def test_links_and_inline_data_are_left_alone(self):
        item = _qti_item(
            "a",
            '<a href="https://example.org/x">x</a><a href="mailto:a@b.c">m</a>'
            '<a href="#top">t</a><img src="data:image/png;base64,iVBORw0KGgo="/>',
        )
        tree = self._ingest([("A", _QTI_ITEM, "a.xml")], {"a.xml": item})
        (leaf,) = tree["children"]
        (question,) = leaf["questions"]
        assert question["raw_data"] == item
        assert question["files"] == []
