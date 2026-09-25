"""Tests for audio and video compression in archive files."""

import base64
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote

import pytest
import requests
from bs4 import BeautifulSoup
from le_utils.constants import content_kinds
from le_utils.constants import format_presets
from le_utils.constants import licenses
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
from ricecooker.utils.references import DEFAULT_MAPPERS

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
        # references are staged with it, and the entry is recorded for Kolibri.
        leaf = leaves[0]
        entry = leaf["extra_fields"]["options"]["entry"]
        assert entry.endswith(".html") and "/" in entry
        with zipfile.ZipFile(leaf["files"][0]["path"]) as zf:
            names = zf.namelist()
        assert entry in names
        assert any(n.endswith(".css") for n in names)
        assert any(n.endswith((".gif", ".png", ".jpg")) for n in names)

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
        # eXe's residual jQuery/effects and .js/.css members keep pages off KPUB.
        assert {f.get_preset() for leaf in leaves for f in leaf.files} == {
            format_presets.HTML5_ZIP
        }
        # Each leaf is backed by its own sealed zip, not the shared package.
        leaf_filenames = [f.get_filename() for leaf in leaves for f in leaf.files]
        assert len(leaf_filenames) == len(set(leaf_filenames))
        assert set(leaf_filenames) <= set(files_to_upload)
