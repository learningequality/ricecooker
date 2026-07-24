"""
To avoid making the pipeline overly convoluted, these handlers
both validate and convert files.
"""

import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import field
from typing import Dict
from typing import Optional
from typing import Union
from xml.etree import ElementTree

import filetype
import html5lib
from html5lib.html5parser import ParseError
from le_utils.constants import content_kinds
from le_utils.constants import file_formats
from le_utils.constants import format_presets
from PIL import Image
from PIL import UnidentifiedImageError
from PyPDF2 import PdfFileReader
from PyPDF2.utils import PdfReadError

from ricecooker.config import LOGGER
from ricecooker.exceptions import UnknownFileTypeError
from ricecooker.utils.audio import AudioCompressionError
from ricecooker.utils.audio import compress_audio
from ricecooker.utils.caching import generate_key
from ricecooker.utils.imscp import parse_imscp_manifest
from ricecooker.utils.paths import extract_path_ext
from ricecooker.utils.pipeline.context import ContentNodeMetadata
from ricecooker.utils.pipeline.context import ContextMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.scorm import has_assessment_semantics
from ricecooker.utils.pipeline.scorm import single_media_member
from ricecooker.utils.pipeline.scorm import strip_scorm_boilerplate
from ricecooker.utils.references import DEFAULT_MAPPERS
from ricecooker.utils.references import ReferenceMapper
from ricecooker.utils.references import sanitize_style_css
from ricecooker.utils.references import strip_scripts
from ricecooker.utils.subtitles import build_subtitle_converter_from_file
from ricecooker.utils.subtitles import InvalidSubtitleFormatError
from ricecooker.utils.subtitles import InvalidSubtitleLanguageError
from ricecooker.utils.subtitles import LANGUAGE_CODE_UNKNOWN
from ricecooker.utils.videos import compress_video
from ricecooker.utils.videos import validate_media_file
from ricecooker.utils.videos import VideoCompressionError
from ricecooker.utils.youtube import get_language_with_alpha2_fallback
from ricecooker.utils.zip import create_predictable_zip

from .file_handler import ExtensionMatchingHandler
from .file_handler import StageHandler

CONVERTIBLE_FORMATS = {p.id: p.convertible_formats for p in format_presets.PRESETLIST}

# CSS properties permitted on inline ``style=`` attributes inside a KPUB.
KPUB_STYLE_ALLOWLIST = {"text-align", "color", "background-color"}


class PandocMissingError(Exception):
    """Raised when the pandoc system binary is required but not installed."""


class PandocConversionError(Exception):
    """Raised when pandoc fails to convert a source document."""


def sanitize_kpub_directory(temp_dir):
    """Strip disallowed CSS and scripts from index.html in an extracted KPUB dir, in place."""
    index_path = os.path.join(temp_dir, "index.html")
    try:
        with open(index_path, encoding="utf-8") as fh:
            html = fh.read()
    except (OSError, UnicodeDecodeError):
        return
    html, removed = sanitize_style_css(html, KPUB_STYLE_ALLOWLIST)
    # Hand-authored KPUBs already reject scripts in validate_archive; strip_scripts
    # is here for the pandoc path, whose --standalone template can inject an html5shiv.
    html, script_removed = strip_scripts(html)
    removed += script_removed
    if removed:
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        LOGGER.info("KPUB sanitizer removed disallowed content: %s", ", ".join(removed))


def _seal_directory_to_file(handler, temp_dir, ext):
    """Zip ``temp_dir`` into a predictable archive and stream it into ``handler``'s output file."""
    processed_zip_path = create_predictable_zip(temp_dir)
    with handler.write_file(ext) as fh:
        with open(processed_zip_path, "rb") as zf:
            shutil.copyfileobj(zf, fh)
    os.unlink(processed_zip_path)


class VideoCompressionContextMetadata(ContextMetadata):
    video_settings: Dict[str, Union[str, int]] = field(default_factory=dict)


class MediaCompressionHandler(ExtensionMatchingHandler):
    def get_cache_key(self, path, ffmpeg_settings=None) -> str:
        return generate_key(
            "COMPRESSED",
            self.normalize_path(path),
            settings=ffmpeg_settings or {},
            default=" (default compression)",
        )


class VideoCompressionHandler(MediaCompressionHandler):
    """
    A FileHandler that compresses or converts a video to .mp4 or .webm.
    - If the original file is .mp4 or .webm, keep that same container.
    - Otherwise, convert to .webm.
    - Uses compress_video(...) which also handles mp4 faststart automatically.
    """

    CONTEXT_CLASS = VideoCompressionContextMetadata

    SUPPORTED_VIDEO_EXTS = {
        file_formats.MP4,
        file_formats.WEBM,
    }

    EXTENSIONS = SUPPORTED_VIDEO_EXTS | set(
        CONVERTIBLE_FORMATS[format_presets.VIDEO_HIGH_RES]
    )

    HANDLED_EXCEPTIONS = [VideoCompressionError]

    def get_file_kwargs(self, context):
        return [{"ffmpeg_settings": context.video_settings}]

    def handle_file(self, path, ffmpeg_settings=None):
        ffmpeg_settings = ffmpeg_settings or {}

        input_ext = extract_path_ext(path)

        if input_ext in self.SUPPORTED_VIDEO_EXTS:
            output_ext = input_ext
            if not ffmpeg_settings:
                # No compression settings provided, just validate the file.
                is_valid, error = validate_media_file(path)
                if not is_valid:
                    raise InvalidFileException(
                        f"Video file {path} did not pass verification with error: {error}"
                    )
                return
        else:
            output_ext = file_formats.WEBM

        with self.write_file(output_ext) as temp_outfile:
            compress_video(path, temp_outfile.name, overwrite=True, **ffmpeg_settings)


class AudioCompressionContextMetadata(ContextMetadata):
    audio_settings: Dict[str, Union[str, int]] = field(default_factory=dict)


class AudioCompressionHandler(MediaCompressionHandler):
    """
    A FileHandler that compresses or converts an audio file to .mp3.
    - If the original file is .mp3, we keep that container.
    - Otherwise, we convert to .mp3.
    - Uses compress_audio(...) internally.
    """

    CONTEXT_CLASS = AudioCompressionContextMetadata

    SUPPORTED_AUDIO_EXTS = {
        file_formats.MP3,
    }

    EXTENSIONS = SUPPORTED_AUDIO_EXTS | set(CONVERTIBLE_FORMATS[format_presets.AUDIO])

    HANDLED_EXCEPTIONS = [AudioCompressionError]

    def get_file_kwargs(self, context):
        return [{"ffmpeg_settings": context.audio_settings}]

    def handle_file(self, path, ffmpeg_settings=None):
        ffmpeg_settings = ffmpeg_settings or {}

        ext = extract_path_ext(path)

        if ext in self.SUPPORTED_AUDIO_EXTS:
            if not ffmpeg_settings:
                # No compression settings provided, just validate the file.
                is_valid, error = validate_media_file(path)
                if not is_valid:
                    raise InvalidFileException(
                        f"Audio file {path} did not pass verification with error: {error}"
                    )
                return

        output_ext = file_formats.MP3

        with self.write_file(output_ext) as temp_outfile:
            compress_audio(path, temp_outfile.name, overwrite=True, **ffmpeg_settings)


class ArchiveProcessingContextMetadata(ContextMetadata):
    audio_settings: Dict[str, Union[str, int]] = field(default_factory=dict)
    video_settings: Dict[str, Union[str, int]] = field(default_factory=dict)


class ArchiveProcessingBaseHandler(ExtensionMatchingHandler):
    CONTEXT_CLASS = ArchiveProcessingContextMetadata

    # Mappers for finding and rewriting external references before
    # create_predictable_zip seals the archive. Every archive format may embed
    # HTML/CSS, so the generic web mappers are the default; a format with its own
    # reference style (e.g. H5P) extends this with its own mapper.
    REFERENCE_MAPPERS = DEFAULT_MAPPERS

    def get_cache_key(self, path, audio_settings=None, video_settings=None) -> str:
        if not audio_settings and not video_settings:
            return super().get_cache_key(path)
        # Mirror the old compress_files_in_archive logic, which used:
        # generate_key("COMPRESSED", filename, settings=ffmpeg_settings)
        ffmpeg_settings = {}
        if isinstance(audio_settings, dict):
            ffmpeg_settings.update(audio_settings)
        if isinstance(video_settings, dict):
            ffmpeg_settings.update(video_settings)
        return generate_key(
            "COMPRESSED",
            self.normalize_path(path),
            settings=ffmpeg_settings,
            default=" (default compression)",
        )

    @property
    @abstractmethod
    def FILE_TYPE(self) -> str:
        pass

    @abstractmethod
    def validate_archive(self, path: str):
        pass

    def pre_process(self, temp_dir):
        """Hook run on the extracted archive dir before reference resolution. Default no-op."""
        pass

    def _process_archive_dir(self, temp_dir, audio_settings, video_settings):
        """Run pre-processing and external-reference resolution over an extracted dir."""
        # Imported here rather than at module level: archive_assets depends on
        # this package's exceptions, so a top-level import would be circular.
        from ricecooker.utils.archive_assets import ArchiveProcessor

        # pre_process runs before reference resolution: a url() inside a <style> block or
        # a non-allowlisted style= would otherwise be downloaded, then orphaned when the
        # sanitizer strips the content that referenced it.
        self.pre_process(temp_dir)

        ArchiveProcessor(
            temp_dir,
            self.get_pipeline(),
            convert_stage=self.parent,
            mappers=self.REFERENCE_MAPPERS,
            audio_settings=audio_settings,
            video_settings=video_settings,
        ).process()

    def handle_file(self, path, audio_settings=None, video_settings=None):
        self.validate_archive(path)

        ext = extract_path_ext(path)

        # TemporaryDirectory removes the extracted (untrusted) content on exit, even on error.
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(temp_dir)

            self._process_archive_dir(temp_dir, audio_settings, video_settings)

            _seal_directory_to_file(self, temp_dir, ext)

    @contextmanager
    def open_and_verify_archive(self, path):
        try:
            with zipfile.ZipFile(path) as zf:
                yield zf
        except zipfile.BadZipFile:
            raise InvalidFileException(
                f"File {path} is not a valid {self.FILE_TYPE} file, it is not a valid zip archive."
            )

    def read_file_from_archive(self, zf, filepath):
        try:
            return zf.read(filepath)
        except KeyError:
            raise InvalidFileException(
                f"File {zf.filename} is not a valid {self.FILE_TYPE} file, {filepath} is missing."
            )

    def _validate_index_html_body(self, zf, path, index_path="index.html"):
        """Validate that the entry HTML exists and has a non-empty body."""
        index_html = self.read_file_from_archive(zf, index_path)
        try:
            dom = html5lib.parse(index_html, namespaceHTMLElements=False)
            body = dom.find("body")
            if body is None:
                raise InvalidFileException(
                    f"File {path} is not a valid {self.FILE_TYPE} file, {index_path} is missing a body element."
                )
            # Check that the body has at least one child element
            # for some reason it seems like comments don't get a string tag attribute
            body_children = [
                c for c in body.iter() if isinstance(c.tag, str) and c.tag != "body"
            ]
            if not (body.text and body.text.strip()) and not body_children:
                raise InvalidFileException(
                    f"File {path} is not a valid {self.FILE_TYPE} file, {index_path} is empty."
                )
            return dom
        except ParseError:
            raise InvalidFileException(
                f"File {path} is not a valid {self.FILE_TYPE} file, {index_path} is not well-formed."
            )


def _find_common_root(names):
    """Return the common parent directory shared by all file paths.

    Ported from Studio's ``findCommonRoot`` (frontend/shared/utils/zipFile.js).
    ``names`` are POSIX-style, non-directory archive member paths.
    """
    paths = [n.split("/")[:-1] for n in names]
    if not paths:
        return ""
    if len(paths) == 1:
        return "/".join(paths[0])
    first = paths[0]
    common = []
    for i, part in enumerate(first):
        for other in paths[1:]:
            if i >= len(other) or other[i] != part:
                return "/".join(common)
        common.append(part)
    return "/".join(common)


def _find_entry_html(names):
    """Return the archive member that is the HTML entry point, or None.

    Ported from Studio's ``findFirstHtml`` (frontend/shared/utils/zipFile.js):
    prefer ``index.html`` at the common-root-stripped root, then any
    ``index.html``, then the shallowest / shortest-named ``.html`` file.
    """
    html_files = [n for n in names if n.lower().endswith(".html")]
    if not html_files:
        return None
    common_root = _find_common_root(names)
    prefix = common_root + "/" if common_root else ""
    normalized = [
        (n, n[len(prefix) :] if prefix and n.startswith(prefix) else n)
        for n in html_files
    ]
    for original, norm in normalized:
        if norm == "index.html":
            return original
    for original, norm in normalized:
        if norm.split("/")[-1] == "index.html":
            return original
    normalized.sort(key=lambda t: (t[1].count("/"), len(t[1])))
    return normalized[0][0]


def kpub_disqualifiers(zf, entry="index.html", index_html=None):
    """Return the reasons ``zf`` fails the KPUB criteria; empty list ⇒ it qualifies.

    A KPUB is static prose: it must have a non-empty ``entry`` body and carry no
    inline ``<script>``, ``.js`` member, or ``.css`` member. ``index_html`` lets a
    caller judge already-transformed markup (e.g. SCORM boilerplate discounted)
    while the physical member checks still run against ``zf``.
    """
    reasons = []
    if index_html is None:
        try:
            index_html = zf.read(entry)
        except KeyError:
            return [f"{entry} is missing."]
    if isinstance(index_html, bytes):
        index_html = index_html.decode("utf-8", errors="replace")

    try:
        dom = html5lib.parse(index_html, namespaceHTMLElements=False)
    except ParseError:
        return [f"{entry} is not well-formed."]

    body = dom.find("body")
    if body is None:
        reasons.append(f"{entry} is missing a body element.")
    else:
        body_children = [
            c for c in body.iter() if isinstance(c.tag, str) and c.tag != "body"
        ]
        if not (body.text and body.text.strip()) and not body_children:
            reasons.append(f"{entry} is empty.")

    if next(dom.iter("script"), None) is not None:
        reasons.append("inline JavaScript (<script> tags) is not allowed.")

    names = zf.namelist()
    if any(n.lower().endswith(".js") for n in names):
        reasons.append("JavaScript files (.js) are not allowed.")
    if any(n.lower().endswith(".css") for n in names):
        reasons.append("external CSS files (.css) are not allowed.")

    return reasons


class HTML5ConversionHandler(ArchiveProcessingBaseHandler):
    EXTENSIONS = {file_formats.HTML5}
    FILE_TYPE = "HTML5"

    def _qualifies_as_kpub(self, path, entry):
        """A static-article HTML5 zip is promoted to a KPUB; anything with scripts,
        JS/CSS members, or a non-root entry stays an HTML5 zip."""
        if entry != "index.html":
            return False
        with zipfile.ZipFile(path) as zf:
            # Discount SCORM plumbing before judging inline scripts; the wrapper
            # .js members it leaves behind still disqualify a genuine SCORM package.
            discounted = strip_scorm_boilerplate(
                zf.read(entry).decode("utf-8", errors="replace")
            )
            return not kpub_disqualifiers(zf, entry, index_html=discounted)

    def handle_file(self, path, audio_settings=None, video_settings=None):
        prepared_path, entry = self._prepare_archive(path)
        promote = False
        try:
            self.validate_archive(prepared_path)
            promote = self._qualifies_as_kpub(prepared_path, entry)
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(prepared_path) as zf:
                    zf.extractall(temp_dir)
                self._process_archive_dir(temp_dir, audio_settings, video_settings)
                if promote:
                    sanitize_kpub_directory(temp_dir)
                    _seal_directory_to_file(self, temp_dir, file_formats.HTML5_ARTICLE)
                else:
                    _seal_directory_to_file(self, temp_dir, file_formats.HTML5)
        finally:
            if prepared_path != path and os.path.exists(prepared_path):
                os.unlink(prepared_path)
        # A promoted KPUB always has an index.html entry, so no entry hint is needed.
        # Mirror Studio otherwise: when the entry point is not index.html at the
        # root, record it in extra_fields.options.entry so Kolibri loads it.
        if not promote and entry and entry != "index.html":
            return FileMetadata(
                content_node_metadata=ContentNodeMetadata(
                    extra_fields={"options": {"entry": entry}}
                )
            )
        return None

    def validate_archive(self, path: str):
        with self.open_and_verify_archive(path) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            entry = _find_entry_html(names)
            if entry is None:
                raise InvalidFileException(
                    f"File {path} is not a valid {self.FILE_TYPE} file, "
                    "no HTML file was found in the archive."
                )
            self._validate_index_html_body(zf, path, entry)

    def _prepare_archive(self, path):
        """Denest a zip whose files all share a common parent directory
        (mirroring Studio's ``cleanHTML5Zip``), and return the path to use
        along with the detected HTML entry point.

        Returns ``(path, entry)`` unchanged when there is nothing to strip;
        otherwise returns the path to a denested temporary zip.
        """
        try:
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
        except zipfile.BadZipFile:
            return path, None  # let validate_archive raise the standard error

        common_root = _find_common_root(names)
        if not common_root:
            return path, _find_entry_html(names)

        prefix = common_root + "/"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name
        with (
            zipfile.ZipFile(path) as zin,
            zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout,
        ):
            for name in names:
                zout.writestr(name[len(prefix) :], zin.read(name))
        denested_names = [n[len(prefix) :] for n in names]
        return tmp_path, _find_entry_html(denested_names)


def _map_h5p_paths(data, fn, urls):
    """Walk an H5P ``content.json`` structure, applying ``fn`` to ``path`` values.

    Recurses dicts and lists. Every string under a ``"path"`` key is a resource
    reference: recorded in ``urls`` and replaced with ``fn(value)``.
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "path" and isinstance(value, str):
                urls.append(value)
                result[key] = fn(value)
            else:
                result[key] = _map_h5p_paths(value, fn, urls)
        return result
    if isinstance(data, list):
        return [_map_h5p_paths(item, fn, urls) for item in data]
    return data


class H5PContentMapper(ReferenceMapper):
    """Maps external ``path`` references in an H5P ``content/content.json``.

    H5P stores references as ``path`` values in a JSON manifest at a fixed
    location, so this mapper matches that one file by path rather than extension.
    """

    CONTENT_JSON = "content/content.json"

    def handles(self, path: str) -> bool:
        return path.replace(os.sep, "/") == self.CONTENT_JSON

    def map(self, content: str, fn):
        urls = []
        data = _map_h5p_paths(json.loads(content), fn, urls)
        return json.dumps(data, ensure_ascii=False), urls


class H5PConversionHandler(ArchiveProcessingBaseHandler):
    EXTENSIONS = {file_formats.H5P}
    FILE_TYPE = "H5P"
    REFERENCE_MAPPERS = DEFAULT_MAPPERS + (H5PContentMapper(),)

    def validate_archive(self, path: str):
        with self.open_and_verify_archive(path) as zf:
            h5p_json = self.read_file_from_archive(zf, "h5p.json")
            try:
                json.loads(h5p_json)
            except json.JSONDecodeError:
                raise InvalidFileException(
                    f"File {path} is not a valid H5P file, h5p.json is not valid JSON."
                )
            content_json = self.read_file_from_archive(zf, "content/content.json")
            try:
                json.loads(content_json)
            except json.JSONDecodeError:
                raise InvalidFileException(
                    f"File {path} is not a valid H5P file, content/content.json is not valid JSON."
                )


class EPUBConversionHandler(ArchiveProcessingBaseHandler):
    EXTENSIONS = {file_formats.EPUB}
    FILE_TYPE = "EPUB"

    def _validate_mimetype(self, zf, path):
        mimetype = self.read_file_from_archive(zf, "mimetype")
        try:
            mimetype = mimetype.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise InvalidFileException(
                f"File {path} is not a valid EPUB file, mimetype file is not UTF-8 encoded."
            )
        if mimetype != "application/epub+zip":
            raise InvalidFileException(
                f"File {path} is not a valid EPUB file, mimetype is incorrect."
            )

    def _get_opf_path(self, zf, path):
        # Then read the container manifest to confirm it exists and get the path to the OPF file.
        container_file = self.read_file_from_archive(zf, "META-INF/container.xml")
        try:
            container = ET.fromstring(container_file)
            rootfiles = container.findall(
                ".//ns:rootfile",
                {"ns": "urn:oasis:names:tc:opendocument:xmlns:container"},
            )
            if not rootfiles:
                raise InvalidFileException(
                    f"File {path} is not a valid EPUB file, rootfile is missing from container manifest."
                )
            opf_path = rootfiles[0].get("full-path")
            if not opf_path:
                raise InvalidFileException(
                    f"File {path} is not a valid EPUB file, rootfile path is empty."
                )
            return opf_path
        except ET.ParseError:
            raise InvalidFileException(
                f"File {path} is not a valid EPUB file, container manifest is not well-formed."
            )

    def _validate_opf(self, zf, path, opf_path):
        # If the container manifest is valid, read the OPF file and confirm it exists and has a manifest.
        opf_file = self.read_file_from_archive(zf, opf_path)
        try:
            opf = ET.fromstring(opf_file)
            manifest = opf.find(
                ".//ns:manifest", {"ns": "http://www.idpf.org/2007/opf"}
            )
            if manifest is None:
                raise InvalidFileException(
                    f"File {path} is not a valid EPUB file, manifest is missing from OPF."
                )
        except ET.ParseError:
            raise InvalidFileException(
                f"File {path} is not a valid EPUB file, OPF file is not well-formed."
            )

    def validate_archive(self, path: str):
        with self.open_and_verify_archive(path) as zf:
            self._validate_mimetype(zf, path)
            opf_path = self._get_opf_path(zf, path)
            self._validate_opf(zf, path, opf_path)


class KPUBConversionHandler(ArchiveProcessingBaseHandler):
    EXTENSIONS = {file_formats.HTML5_ARTICLE}
    FILE_TYPE = "KPUB"

    def pre_process(self, temp_dir):
        sanitize_kpub_directory(temp_dir)

    def validate_archive(self, path: str):
        with self.open_and_verify_archive(path) as zf:
            reasons = kpub_disqualifiers(zf)
            if reasons:
                raise InvalidFileException(
                    f"File {path} is not a valid {self.FILE_TYPE} file, {reasons[0]}"
                )


class BloomConversionHandler(ArchiveProcessingBaseHandler):
    EXTENSIONS = {file_formats.BLOOMPUB, file_formats.BLOOMD}
    FILE_TYPE = "Bloom"

    def validate_archive(self, path: str):
        with self.open_and_verify_archive(path) as zf:
            # Check meta.json exists and is valid
            meta = self.read_file_from_archive(zf, "meta.json")
            try:
                meta = json.loads(meta)
                required_meta_fields = ["bookInstanceId", "title"]
                missing_fields = [f for f in required_meta_fields if f not in meta]
                if missing_fields:
                    raise InvalidFileException(
                        f"File {path} is not a valid bloom file, meta.json missing required fields: {', '.join(missing_fields)}"
                    )
            except json.JSONDecodeError:
                raise InvalidFileException(
                    f"File {path} is not a valid bloom file, meta.json is not valid JSON."
                )

            # Check for at least one .htm file
            htm_files = [f for f in zf.namelist() if f.lower().endswith(".htm")]
            if not htm_files:
                raise InvalidFileException(
                    f"File {path} is not a valid bloom file, no .htm files found."
                )


class PDFValidationHandler(ExtensionMatchingHandler):
    """
    A FileHandler that validates PDF files.
    """

    EXTENSIONS = {file_formats.PDF}

    def handle_file(self, path):
        try:
            with open(path, "rb") as f:
                pdf = PdfFileReader(f)
                if pdf.getNumPages() == 0:
                    raise InvalidFileException(f"PDF file {path} has no pages.")
        except PdfReadError as e:
            raise InvalidFileException(f"PDF file {path} did not pass validation: {e}")
        except FileNotFoundError:
            raise InvalidFileException(f"File not found at path: {path}")


class ImageConversionHandler(ExtensionMatchingHandler):
    """
    A FileHandler that converts image files to supported formats.
    """

    SUPPORTED_IMAGE_EXTENSIONS = {
        file_formats.PNG,
        file_formats.JPG,
        file_formats.JPEG,
        file_formats.GIF,
    }

    # Add all supported image extensions from PIL except for PDF
    EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | {
        key.strip(".") for key in Image.registered_extensions() if key != ".pdf"
    }

    def handle_file(self, path):
        preferred_extension = extract_path_ext(path)
        file_type_guess = filetype.guess(path)
        extension = file_type_guess.extension if file_type_guess else None
        if extension is None and not preferred_extension:
            raise UnknownFileTypeError(
                "Unable to determine file type of {}".format(path)
            )
        if extension == file_formats.JPEG and preferred_extension == file_formats.JPG:
            extension = preferred_extension
        try:
            with Image.open(path) as im:
                im.verify()
            if extension not in self.SUPPORTED_IMAGE_EXTENSIONS:
                tempf = tempfile.NamedTemporaryFile(
                    suffix=".{}".format(file_formats.PNG), delete=False
                )
                tempf.close()
                extension = file_formats.PNG
                with self.write_file(extension) as tempf:
                    with Image.open(path) as im:
                        im.convert("RGB").save(tempf, extension)
        except UnidentifiedImageError as e:
            raise InvalidFileException(
                f"Image file {path} did not pass verification: {e}"
            )


class SVGValidationHandler(ExtensionMatchingHandler):
    """
    We don't do any conversion on SVG files, but we can validate them.
    """

    EXTENSIONS = {file_formats.SVG}

    def handle_file(self, path):
        try:
            ElementTree.parse(path)
        except ElementTree.ParseError as e:
            raise InvalidFileException(
                f"SVG file {path} did not pass verification: {e}"
            )


class SubtitleContextMetadata(ContextMetadata):
    language: str
    subtitle_format: Optional[str] = None


class SubtitleConversionHandler(ExtensionMatchingHandler):
    """
    A FileHandler that converts subtitle files to .vtt format.
    """

    CONTEXT_CLASS = SubtitleContextMetadata

    EXTENSIONS = {file_formats.VTT} | set(
        CONVERTIBLE_FORMATS[format_presets.VIDEO_SUBTITLE]
    )

    HANDLED_EXCEPTIONS = [InvalidSubtitleFormatError, InvalidSubtitleLanguageError]

    def get_cache_key(
        self, path: str, language: str = None, subtitle_format: str = None
    ) -> str:
        return super().get_cache_key(path)

    def handle_file(self, path, language=None, subtitle_format=None):
        if language is None:
            raise ValueError("Subtitles must have a language specified.")

        converter = build_subtitle_converter_from_file(path, in_format=subtitle_format)

        # We'll assume the provided file is in the passed language in this case
        if len(converter.get_language_codes()) == 1 and converter.has_language(
            LANGUAGE_CODE_UNKNOWN
        ):
            converter.replace_unknown_language(language)

        convert_lang_code = language

        # Language is not present, let's try different codes
        if not converter.has_language(language):
            input_language = get_language_with_alpha2_fallback(language)
            for lang_code in converter.get_language_codes():
                lang_obj = get_language_with_alpha2_fallback(lang_code)

                if lang_obj and lang_obj.code == input_language.code:
                    convert_lang_code = lang_code
                    break
            else:
                raise InvalidSubtitleLanguageError(
                    "Missing language '{}' in subtitle file".format(language)
                )
        with self.write_file(file_formats.VTT) as fh:
            converter.write(fh.name, convert_lang_code)
        return FileMetadata(language=convert_lang_code)


class DocumentConversionHandler(ExtensionMatchingHandler):
    """Convert article-style documents to KPUB via pandoc, then sanitize."""

    EXTENSIONS = {"docx", "odt", "rtf", "md", "markdown"}
    HANDLED_EXCEPTIONS = [PandocConversionError]

    def handle_file(self, path):
        if shutil.which("pandoc") is None:
            raise PandocMissingError(
                "pandoc is required to convert documents (.docx/.odt/.rtf/.md/.markdown) "
                "to KPUB. Install pandoc — see docs/installation.md."
            )
        # cwd=temp_dir below, so keep the input path absolute.
        src = os.path.abspath(path)
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                subprocess.run(
                    [
                        "pandoc",
                        src,
                        "--standalone",
                        "--mathml",
                        "--extract-media=media",
                        "-o",
                        "index.html",
                    ],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                raise PandocConversionError(
                    f"pandoc failed to convert {path}: {e.stderr}"
                )
            # pandoc --extract-media localizes embedded media only; unlike an
            # uploaded KPUB, remote <img> refs are not downloaded (out of scope).
            sanitize_kpub_directory(temp_dir)
            _seal_directory_to_file(self, temp_dir, file_formats.HTML5_ARTICLE)


# Presets whose files ride alongside a primary file (thumbnails, subtitles); they
# never define a node's kind.
SUPPLEMENTARY_PRESETS = frozenset(
    p.id for p in format_presets.PRESETLIST if p.supplementary
)


def _content_node_field(content_node_metadata, key):
    """Read ``key`` off a ContentNodeMetadata that may be an object or a dict.

    A sub-pipeline result carries it as a dict (``merge`` round-trips through
    ``to_dict``); a freshly built one is the dataclass.
    """
    if content_node_metadata is None:
        return None
    if isinstance(content_node_metadata, dict):
        return content_node_metadata.get(key)
    return getattr(content_node_metadata, key, None)


def _summarize_leaf(sub):
    """Reduce a sub-pipeline result to ``(kind, file dicts, extra_fields)``.

    The node's kind/extra_fields come from its primary (non-supplementary) file;
    every file dict is retained so the leaf is backed by its own sealed files.
    """
    files = [fm.to_dict() for fm in sub]
    for fm in sub:
        if fm.preset in SUPPLEMENTARY_PRESETS:
            continue
        return (
            _content_node_field(fm.content_node_metadata, "kind"),
            files,
            _content_node_field(fm.content_node_metadata, "extra_fields"),
        )
    return None, files, None


def _contained_path(root, member):
    """Resolve ``member`` under ``root``; return the path, or None if it escapes.

    Manifest hrefs/file paths are untrusted — a ``../`` traversal must not let a
    package read files from outside its extracted directory into the decomposed
    output (the staging copy already guards its write side the same way).
    """
    root_abs = os.path.abspath(root)
    target = os.path.abspath(os.path.join(root_abs, member))
    if target != root_abs and not target.startswith(root_abs + os.sep):
        return None
    return target


class IMSCPConversionHandler(ExtensionMatchingHandler):
    """Decompose an IMS Content Package (incl. SCORM) into a native node subtree.

    The ``imsmanifest.xml`` drives a topic tree; each webcontent resource is
    classified up a conservative ladder — native media, else HTML5/KPUB zip —
    with assessment resources rejected. Every surviving leaf re-enters the
    pipeline to be sealed into its own file, so no leaf is backed by the whole
    package zip. Registered before ``HTML5ConversionHandler`` (which claims any
    ``.zip``) so IMSCP packages are decomposed rather than wrapped whole.
    """

    EXTENSIONS = {file_formats.HTML5}

    def should_handle(self, path):
        try:
            if extract_path_ext(path) != file_formats.HTML5:
                return False
            with zipfile.ZipFile(path) as zf:
                return "imsmanifest.xml" in zf.namelist()
        except (ValueError, zipfile.BadZipFile):
            return False

    def handle_file(self, path, audio_settings=None, video_settings=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(temp_dir)
            manifest = parse_imscp_manifest(temp_dir)
            children = self._build_nodes(manifest.get("children"), temp_dir)
        return FileMetadata(
            content_node_metadata=ContentNodeMetadata(
                kind=content_kinds.TOPIC,
                title=manifest.get("title"),
                children=children,
            )
        )

    def _build_nodes(self, nodes, temp_dir):
        built = [self._build_node(node, temp_dir) for node in nodes or []]
        return [node for node in built if node is not None]

    def _build_node(self, node_dict, temp_dir):
        if node_dict.get("children"):
            # A topic whose leaves were all rejected keeps its (empty) folder.
            return {
                "source_id": node_dict["source_id"],
                "title": node_dict.get("title") or node_dict["source_id"],
                "children": self._build_nodes(node_dict["children"], temp_dir),
            }
        return self._build_leaf(node_dict, temp_dir)

    def _build_leaf(self, node_dict, temp_dir):
        source_id = node_dict.get("source_id")
        if node_dict.get("type") != "webcontent" or not node_dict.get("index_file"):
            LOGGER.warning(
                "IMSCP: skipping unsupported resource %s (type=%s)",
                source_id,
                node_dict.get("type"),
            )
            return None

        index_path = _contained_path(temp_dir, node_dict["index_file"])
        if index_path is None:
            LOGGER.warning(
                "IMSCP: skipping resource %s, index path escapes package: %s",
                source_id,
                node_dict.get("index_file"),
            )
            return None
        try:
            with open(index_path, "rb") as fh:
                index_html = fh.read().decode("utf-8", errors="replace")
        except OSError:
            LOGGER.warning(
                "IMSCP: skipping resource %s, index file missing: %s",
                source_id,
                node_dict.get("index_file"),
            )
            return None

        members = node_dict.get("files") or []
        if has_assessment_semantics(index_html, members, node_dict):
            LOGGER.warning("IMSCP: rejecting assessment resource %s", source_id)
            return None

        media = single_media_member({**node_dict, "index_html": index_html})
        if media:
            media_path = _contained_path(temp_dir, media)
            if media_path is None:
                LOGGER.warning(
                    "IMSCP: skipping resource %s, media path escapes package: %s",
                    source_id,
                    media,
                )
                return None
            sub = self.get_pipeline().execute(media_path)
        else:
            sub = self._process_html5_leaf(node_dict, temp_dir)
        if not sub:
            LOGGER.warning("IMSCP: skipping resource %s, produced no files", source_id)
            return None

        kind, files, extra_fields = _summarize_leaf(sub)
        leaf = {
            "source_id": source_id,
            "title": node_dict.get("title") or source_id,
            "kind": kind,
            "files": files,
        }
        if extra_fields:
            leaf["extra_fields"] = extra_fields
        return leaf

    def _process_html5_leaf(self, node_dict, temp_dir):
        """Seal the resource's own members into a zip and process it as HTML5/KPUB."""
        with tempfile.TemporaryDirectory() as staging:
            self._stage_leaf(node_dict, temp_dir, staging)
            zip_path = create_predictable_zip(staging)
        try:
            return self.get_pipeline().execute(zip_path)
        finally:
            os.unlink(zip_path)

    def _stage_leaf(self, node_dict, temp_dir, dest_dir):
        """Copy the resource's members into ``dest_dir`` (relative paths preserved),
        guaranteeing a root ``index.html`` entry."""
        dest_root = os.path.abspath(dest_dir)
        for member in node_dict.get("files") or []:
            # Guard against a manifest path escaping the package (read side) or
            # the staging dir (write side).
            src = _contained_path(temp_dir, member)
            dst = os.path.abspath(os.path.join(dest_dir, member))
            if src is None or not os.path.isfile(src):
                continue
            if not dst.startswith(dest_root + os.sep):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
        index_dst = os.path.join(dest_dir, "index.html")
        if not os.path.isfile(index_dst):
            index_src = _contained_path(temp_dir, node_dict["index_file"])
            if index_src and os.path.isfile(index_src):
                shutil.copyfile(index_src, index_dst)


class ConversionStageHandler(StageHandler):
    STAGE = "CONVERT"
    DEFAULT_CHILDREN = [
        SubtitleConversionHandler,
        SVGValidationHandler,
        PDFValidationHandler,
        ImageConversionHandler,
        BloomConversionHandler,
        EPUBConversionHandler,
        H5PConversionHandler,
        IMSCPConversionHandler,
        HTML5ConversionHandler,
        DocumentConversionHandler,
        KPUBConversionHandler,
        VideoCompressionHandler,
        AudioCompressionHandler,
    ]
