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

import pytest
import requests
from bs4 import BeautifulSoup
from le_utils.constants import format_presets

from ricecooker import config
from ricecooker.classes.files import EPubFile
from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.utils import archive_assets
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.convert import _find_common_root
from ricecooker.utils.pipeline.convert import _find_entry_html
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

    with patch.object(config, "DOWNLOAD_SESSION", SimpleNamespace(get=get)):
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
        """A ``data:`` URI is localized: decoded to a real file, ref rewritten."""
        data_uri = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()

        class _StubPipeline:
            """Decodes the data: URI to a real png and returns its metadata."""

            def __init__(self, storage):
                self._storage = storage

            def execute(self, url, **kwargs):
                _, _, b64 = url.partition(",")
                out = os.path.join(self._storage, "decoded.png")
                with open(out, "wb") as fh:
                    fh.write(base64.b64decode(b64))
                return [SimpleNamespace(path=out)]

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as storage,
        ):
            index_path = os.path.join(tmpdir, "index.html")
            with open(index_path, "w") as fh:
                fh.write('<html><body><img src="{}"></body></html>'.format(data_uri))
            archive_assets.ArchiveProcessor(tmpdir, _StubPipeline(storage)).process()

            pngs = [n for n in os.listdir(tmpdir) if n.endswith(".png")]
            assert len(pngs) == 1
            index = open(index_path).read()
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
