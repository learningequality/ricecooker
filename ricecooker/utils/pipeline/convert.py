"""
To avoid making the pipeline overly convoluted, these handlers
both validate and convert files.
"""

import json
import os
import posixpath
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import Optional
from typing import Union
from xml.etree import ElementTree

import filetype
import html5lib
from html5lib.html5parser import ParseError
from le_utils.constants import file_formats
from le_utils.constants import format_presets
from PIL import Image
from PIL import UnidentifiedImageError
from PyPDF2 import PdfFileReader
from PyPDF2.utils import PdfReadError

from ricecooker import config
from ricecooker.config import LOGGER
from ricecooker.exceptions import UnknownFileTypeError
from ricecooker.utils.archive_dependencies import SharedAssetExtractor
from ricecooker.utils.audio import AudioCompressionError
from ricecooker.utils.audio import compress_audio
from ricecooker.utils.caching import generate_key
from ricecooker.utils.imscp import collapse_single_children
from ricecooker.utils.imscp import contained_path
from ricecooker.utils.imscp import IMSCP_MANIFEST
from ricecooker.utils.imscp import IMSCPPackage
from ricecooker.utils.imscp import is_qti_resource
from ricecooker.utils.imscp import lom_content_fields
from ricecooker.utils.imscp import node_content_fields
from ricecooker.utils.imscp import parse_imscp_manifest
from ricecooker.utils.paths import extract_path_ext
from ricecooker.utils.pipeline.context import ContentNodeMetadata
from ricecooker.utils.pipeline.context import ContextMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.references import DEFAULT_MAPPERS
from ricecooker.utils.references import ReferenceMapper
from ricecooker.utils.references import sanitize_style_css
from ricecooker.utils.references import strip_scripts
from ricecooker.utils.references import strip_stylesheet_links
from ricecooker.utils.scorm import boilerplate_script_members
from ricecooker.utils.scorm import has_assessment_semantics
from ricecooker.utils.scorm import single_media_member
from ricecooker.utils.scorm import strip_scorm_boilerplate
from ricecooker.utils.storage import copy_file_to_storage
from ricecooker.utils.subtitles import build_subtitle_converter_from_file
from ricecooker.utils.subtitles import InvalidSubtitleFormatError
from ricecooker.utils.subtitles import InvalidSubtitleLanguageError
from ricecooker.utils.subtitles import LANGUAGE_CODE_UNKNOWN
from ricecooker.utils.videos import compress_video
from ricecooker.utils.videos import validate_media_file
from ricecooker.utils.videos import VideoCompressionError
from ricecooker.utils.youtube import get_language_with_alpha2_fallback
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.zip import directory_member_names
from ricecooker.utils.zip import find_common_root
from ricecooker.utils.zip import find_html_entrypoint

from .file_handler import ExtensionMatchingHandler
from .file_handler import StageHandler

CONVERTIBLE_FORMATS = {p.id: p.convertible_formats for p in format_presets.PRESETLIST}

# CSS properties permitted on inline ``style=`` attributes inside a KPUB.
KPUB_STYLE_ALLOWLIST = {"text-align", "color", "background-color"}


class PandocMissingError(Exception):
    """Raised when the pandoc system binary is required but not installed."""


class PandocConversionError(Exception):
    """Raised when pandoc fails to convert a source document."""


def sanitize_kpub_html(html):
    """Strip disallowed CSS and scripts from a KPUB entry document.

    Returns ``(html, removed)`` — descriptors of what was stripped, empty if unchanged.
    """
    html, removed = sanitize_style_css(html, KPUB_STYLE_ALLOWLIST)
    # Hand-authored KPUBs already reject scripts in validate_archive; strip_scripts
    # is here for the pandoc path, whose --standalone template can inject an html5shiv.
    html, script_removed = strip_scripts(html)
    return html, removed + script_removed


def sanitize_kpub_directory(temp_dir, entry="index.html"):
    """Sanitize a KPUB's entry document in place."""
    entry_path = os.path.join(temp_dir, entry)
    try:
        with open(entry_path, encoding="utf-8") as fh:
            html = fh.read()
    except (OSError, UnicodeDecodeError):
        return
    html, removed = sanitize_kpub_html(html)
    if removed:
        with open(entry_path, "w", encoding="utf-8") as fh:
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
    def validate_archive(self, path: str, entry=None):
        pass

    def pre_process(self, temp_dir, entry):
        """Hook run on the extracted archive dir before reference resolution. Default no-op."""
        pass

    def seal_ext(self, temp_dir, ext, entry=None):
        """Extension the processed dir is sealed as. Override to re-classify the output."""
        return ext

    def _process_directory(
        self, directory, audio_settings=None, video_settings=None, members=None
    ):
        """Localize and compress the extracted archive in ``directory`` in place.

        ``members`` limits the download pass to those archive paths.
        """
        # Imported here rather than at module level: archive_assets depends on
        # this package's exceptions, so a top-level import would be circular.
        from ricecooker.utils.archive_assets import ArchiveProcessor

        ArchiveProcessor(
            directory,
            self.get_pipeline(),
            convert_stage=self.parent,
            mappers=self.REFERENCE_MAPPERS,
            audio_settings=audio_settings,
            video_settings=video_settings,
            members=members,
        ).process()

    def _convert_archive(
        self, path, audio_settings, video_settings, entry=None, **seal_kwargs
    ):
        """Validate, extract, process and seal the archive at ``path``."""
        self.validate_archive(path, entry)

        ext = extract_path_ext(path)

        # TemporaryDirectory removes the extracted (untrusted) content on exit, even on error.
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(temp_dir)

            # pre_process runs before reference resolution: a url() inside a <style> block or
            # a non-allowlisted style= would otherwise be downloaded, then orphaned when the
            # sanitizer strips the content that referenced it.
            self.pre_process(temp_dir, entry)

            self._process_directory(temp_dir, audio_settings, video_settings)

            _seal_directory_to_file(
                self, temp_dir, self.seal_ext(temp_dir, ext, entry, **seal_kwargs)
            )

    def handle_file(self, path, audio_settings=None, video_settings=None):
        self._convert_archive(path, audio_settings, video_settings)

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


def _parse_entry(html, entry):
    """Parse ``html``; return ``(dom, reason)``, with ``reason`` None when the body is usable."""
    try:
        dom = html5lib.parse(html, namespaceHTMLElements=False)
    except ParseError:
        return None, f"{entry} is not well-formed."
    return dom, _empty_body_reason(dom, entry)


def _empty_body_reason(dom, entry):
    """Why ``dom`` has no usable body, or None when it has one."""
    body = dom.find("body")
    if body is None:
        return f"{entry} is missing a body element."
    # For some reason it seems like comments don't get a string tag attribute.
    body_children = [
        c for c in body.iter() if isinstance(c.tag, str) and c.tag != "body"
    ]
    if not (body.text and body.text.strip()) and not body_children:
        return f"{entry} is empty."
    return None


def _kpub_disqualifier(names, index_html, entry):
    """The first reason a KPUB candidate fails the criteria; None ⇒ it qualifies.

    A KPUB is static prose: a non-empty ``entry`` body, no inline ``<script>``, no
    ``.js``/``.css`` member. ``index_html`` is separate from ``names`` so a caller
    can judge already-transformed markup against the members that will ship.
    """
    if index_html is None:
        return f"{entry} is missing."
    dom, reason = _parse_entry(index_html, entry)
    if reason:
        return reason
    if next(dom.iter("script"), None) is not None:
        return "inline JavaScript (<script> tags) is not allowed."
    if any(n.lower().endswith(".js") for n in names):
        return "JavaScript files (.js) are not allowed."
    if any(n.lower().endswith(".css") for n in names):
        return "external CSS files (.css) are not allowed."
    return None


def _has_script(html):
    if "<script" not in html.lower():
        return False
    return (
        next(html5lib.parse(html, namespaceHTMLElements=False).iter("script"), None)
        is not None
    )


class WebArchiveContextMetadata(ArchiveProcessingContextMetadata):
    # The entry point, as an archive member path; detected when unset.
    entry: Optional[str] = None


class WebArchiveConversionHandler(ArchiveProcessingBaseHandler):
    """Zip of web content that Kolibri serves from an HTML entry point.

    Denests a single-root zip (mirroring Studio's ``cleanHTML5Zip``) and records
    an entry point other than a root ``index.html`` for the renderer.
    """

    CONTEXT_CLASS = WebArchiveContextMetadata

    def get_cache_key(self, path, entry=None, **kwargs) -> str:
        key = super().get_cache_key(path, **kwargs)
        return f"{key}:entry={entry}" if entry else key

    def entry_point(self, names):
        """The archive member Kolibri should load, or None when there is no HTML."""
        return find_html_entrypoint([n for n in names if not n.endswith("/")])

    def handle_file(
        self, path, audio_settings=None, video_settings=None, entry=None, **seal_kwargs
    ):
        prepared_path, entry = self._prepare_archive(path, entry)
        try:
            self._convert_archive(
                prepared_path, audio_settings, video_settings, entry, **seal_kwargs
            )
        finally:
            if prepared_path != path and os.path.exists(prepared_path):
                os.unlink(prepared_path)
        # Mirror Studio: when the entry point is not index.html at the root,
        # record it in extra_fields.options.entry so Kolibri loads it.
        if entry and entry != "index.html":
            return FileMetadata(
                content_node_metadata=ContentNodeMetadata(
                    extra_fields={"options": {"entry": entry}}
                )
            )
        return None

    def validate_archive(self, path: str, entry=None):
        with self.open_and_verify_archive(path) as zf:
            entry = entry or self.entry_point(zf.namelist())
            if entry is None:
                raise InvalidFileException(
                    f"File {path} is not a valid {self.FILE_TYPE} file, "
                    "no HTML file was found in the archive."
                )
            self._validate_entry(zf, path, entry)

    def entry_disqualifier(self, names, html, entry):
        """Why the entry point is unusable, or None. Default: it lacks a body."""
        return _parse_entry(html, entry)[1]

    def _validate_entry(self, zf, path, entry):
        reason = self.entry_disqualifier(
            zf.namelist(), self.read_file_from_archive(zf, entry), entry
        )
        if reason:
            raise InvalidFileException(
                f"File {path} is not a valid {self.FILE_TYPE} file, {reason}"
            )

    def _prepare_archive(self, path, entry=None):
        """Denest a zip whose files all share a common parent directory
        (mirroring Studio's ``cleanHTML5Zip``), and return the path to use
        along with the HTML entry point: ``entry`` rebased, else detected.

        Returns ``(path, entry)`` unchanged when there is nothing to strip;
        otherwise returns the path to a denested temporary zip.
        """
        try:
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
        except zipfile.BadZipFile:
            return path, None  # let validate_archive raise the standard error

        common_root = find_common_root(names)
        if not common_root:
            return path, entry or self.entry_point(names)

        prefix = common_root + "/"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name
        with (
            zipfile.ZipFile(path) as zin,
            zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout,
        ):
            for name in names:
                zout.writestr(name[len(prefix) :], zin.read(name))
        if entry:
            return tmp_path, entry[len(prefix) :] if entry.startswith(prefix) else entry
        return tmp_path, self.entry_point([n[len(prefix) :] for n in names])


class HTML5ContextMetadata(WebArchiveContextMetadata):
    # Set by callers that fixed the kind (a typed File or node): no KPUB
    # promotion, no IMSCP decomposition.
    preserve_kind: bool = False


class HTML5ConversionHandler(WebArchiveConversionHandler):
    EXTENSIONS = {file_formats.HTML5}
    FILE_TYPE = "HTML5"
    CONTEXT_CLASS = HTML5ContextMetadata

    def get_cache_key(self, path, preserve_kind=False, **kwargs) -> str:
        key = super().get_cache_key(path, **kwargs)
        return key if preserve_kind else f"{key}:promote"

    def seal_ext(self, temp_dir, ext, entry=None, preserve_kind=False):
        if not preserve_kind and self._promote_to_kpub(temp_dir, entry):
            return file_formats.HTML5_ARTICLE
        return ext

    def _promote_to_kpub(self, temp_dir, entry):
        """Rewrite a static-article HTML5 zip into a KPUB in place; True on promotion."""
        plan = self._kpub_plan(temp_dir, entry)
        if plan is None:
            return False
        pages, strippable = plan
        for name, html in pages.items():
            html = strip_stylesheet_links(html)
            if name == entry:
                html, _removed = sanitize_kpub_html(html)
            with open(os.path.join(temp_dir, name), "w", encoding="utf-8") as fh:
                fh.write(html)
        for name in strippable:
            os.unlink(os.path.join(temp_dir, name))
        return True

    def _kpub_plan(self, temp_dir, entry, names=None):
        """``(pages, strippable)`` when the extracted zip is a static article, else None.

        SCORM plumbing and stylesheets are stripped rather than disqualifying:
        neither is content. Genuine scripting on any page keeps the zip HTML5.
        Judged after reference resolution, so downloaded assets count too.
        ``names`` limits the judgement to those members of ``temp_dir``.
        """
        if names is None:
            names = directory_member_names(temp_dir)
        strippable = set(boilerplate_script_members(names)) | {
            name for name in names if name.lower().endswith(".css")
        }
        kept = [name for name in names if name not in strippable]
        # Cheap name check first: most HTML5 apps ship their own .js.
        if any(name.lower().endswith(".js") for name in kept):
            return None
        pages = {}
        for name in names:
            if not name.lower().endswith((".html", ".htm")):
                continue
            try:
                with open(os.path.join(temp_dir, name), encoding="utf-8") as fh:
                    pages[name] = strip_scorm_boilerplate(fh.read())
            except (OSError, UnicodeDecodeError):
                # Re-encoding a non-UTF-8 page would corrupt it.
                return None
        if _kpub_disqualifier(kept, pages.get(entry), entry) is not None:
            return None
        if any(_has_script(html) for name, html in pages.items() if name != entry):
            return None
        return pages, strippable


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

    def validate_archive(self, path: str, entry=None):
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

    def validate_archive(self, path: str, entry=None):
        with self.open_and_verify_archive(path) as zf:
            self._validate_mimetype(zf, path)
            opf_path = self._get_opf_path(zf, path)
            self._validate_opf(zf, path, opf_path)


class KPUBConversionHandler(WebArchiveConversionHandler):
    EXTENSIONS = {file_formats.HTML5_ARTICLE}
    FILE_TYPE = "KPUB"

    def pre_process(self, temp_dir, entry):
        sanitize_kpub_directory(temp_dir, entry)

    def entry_disqualifier(self, names, html, entry):
        return _kpub_disqualifier(names, html, entry)


class BloomConversionHandler(ArchiveProcessingBaseHandler):
    EXTENSIONS = {file_formats.BLOOMPUB, file_formats.BLOOMD}
    FILE_TYPE = "Bloom"

    def validate_archive(self, path: str, entry=None):
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
_SUPPLEMENTARY_PRESETS = frozenset(
    p.id for p in format_presets.PRESETLIST if p.supplementary
)


def _summarize_leaf(sub):
    """Reduce a sub-pipeline result to ``(kind, file dicts, extra_fields)``.

    The node's kind/extra_fields come from its primary (non-supplementary) file;
    every file dict is retained so the leaf is backed by its own sealed files.
    """
    files = [fm.to_dict() for fm in sub]
    for fm in sub:
        if fm.preset in _SUPPLEMENTARY_PRESETS:
            continue
        # merge() round-trips through to_dict(), so this is always a plain dict.
        metadata = fm.content_node_metadata or {}
        return metadata.get("kind"), files, metadata.get("extra_fields")
    return None, files, None


def _manifest_member(names):
    """The package's ``imsmanifest.xml`` member, at the root or under a single wrapping folder."""
    if IMSCP_MANIFEST in names:
        return IMSCP_MANIFEST
    common_root = find_common_root([n for n in names if not n.endswith("/")])
    nested = f"{common_root}/{IMSCP_MANIFEST}" if common_root else None
    return nested if nested in names else None


@dataclass(eq=False)
class _PendingLeaf:
    """An HTML5 resource that seals only after its package's dependency zip."""

    node_dict: dict

    @property
    def entry(self):
        return posixpath.normpath(self.node_dict["index_file"])

    @property
    def members(self):
        return [self.entry] + list(self.node_dict.get("files") or [])


def _pending_leaves(nodes):
    """``nodes``' pending leaves, depth-first (manifest order)."""
    for node in nodes:
        if isinstance(node, _PendingLeaf):
            yield node
        else:
            yield from _pending_leaves(node.get("children", ()))


class IMSCPConversionHandler(HTML5ConversionHandler):
    """Decompose an IMS Content Package (incl. SCORM) into a native node subtree.

    Every surviving leaf re-enters the pipeline to be sealed into its own file, so
    no leaf is backed by the whole package zip. QTI 3.0 tests and items become
    exercises. Must be registered before ``HTML5ConversionHandler``, which
    claims any ``.zip``.
    """

    def should_handle(self, path):
        if not super().should_handle(path):
            return False
        try:
            with zipfile.ZipFile(path) as zf:
                return _manifest_member(zf.namelist()) is not None
        except (OSError, zipfile.BadZipFile):
            return False

    def handle_file(
        self,
        path,
        audio_settings=None,
        video_settings=None,
        entry=None,
        preserve_kind=False,
    ):
        if preserve_kind:
            return super().handle_file(
                path, audio_settings, video_settings, entry, preserve_kind=True
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(path) as zf:
                ims_dir = os.path.join(
                    temp_dir, posixpath.dirname(_manifest_member(zf.namelist()))
                )
                zf.extractall(temp_dir)
            try:
                manifest = parse_imscp_manifest(ims_dir)
            except ET.ParseError as e:
                raise InvalidFileException(
                    f"File {path} is not a valid IMSCP package, its {IMSCP_MANIFEST} could not be parsed: {e}"
                )
            # Every leaf compresses its media like the package would.
            settings = {
                "audio_settings": audio_settings or {},
                "video_settings": video_settings or {},
            }
            package = IMSCPPackage(ims_dir)
            nodes = self._build_nodes(manifest.get("children"), package, settings)
            sealed = self._seal_pending(_pending_leaves(nodes), package, settings)
            # qti imports this module's image handlers.
            from ricecooker.utils.qti import QTIExerciseBuilder

            qti_exercises = QTIExerciseBuilder(package, self.get_pipeline()).exercises(
                manifest
            )
        children = self._finish_nodes(nodes, sealed) + qti_exercises
        if not children:
            raise InvalidFileException(
                f"File {path} is not a valid IMSCP package, every resource was rejected."
            )
        # Package-level LOM rides on the topmost node.
        tree = collapse_single_children(
            {**lom_content_fields(manifest), "children": children}
        )
        if "children" not in tree:
            # A lone resource, which the declaring node becomes.
            tree = {"children": [tree]}
        return FileMetadata(content_node_metadata=ContentNodeMetadata(**tree))

    def _build_nodes(self, nodes, package, settings):
        built = [self._build_node(node, package, settings) for node in nodes or []]
        return [node for node in built if node is not None]

    def _build_node(self, node_dict, package, settings):
        if node_dict.get("children"):
            return {
                **node_content_fields(node_dict),
                "children": self._build_nodes(node_dict["children"], package, settings),
            }
        return self._build_leaf(node_dict, package, settings)

    def _finish_nodes(self, nodes, sealed):
        finished = [self._finish_node(node, sealed) for node in nodes]
        return [node for node in finished if node is not None]

    def _finish_node(self, node, sealed):
        """Swap in ``node``'s sealed leaves, pruning a topic left without any."""
        if isinstance(node, _PendingLeaf):
            return sealed[node]
        if "children" not in node:
            return node
        children = self._finish_nodes(node["children"], sealed)
        if not children:
            LOGGER.warning(
                "IMSCP: skipping topic %s, every resource was rejected",
                node["source_id"],
            )
            return None
        return {**node, "children": children}

    def _build_leaf(self, node_dict, package, settings):
        source_id = node_dict.get("source_id")
        # Built from <resources> by QTIExerciseBuilder.
        if is_qti_resource(node_dict.get("type")):
            return None
        if node_dict.get("type") != "webcontent" or not node_dict.get("index_file"):
            LOGGER.warning(
                "IMSCP: skipping unsupported resource %s (type=%s)",
                source_id,
                node_dict.get("type"),
            )
            return None

        index_path = contained_path(package.directory, node_dict["index_file"])
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

        if has_assessment_semantics(index_html, node_dict.get("masteryscore")):
            LOGGER.warning("IMSCP: rejecting assessment resource %s", source_id)
            return None

        # A resource reducing to one wrapped media file is processed as that file;
        # everything else waits to be sealed into its own HTML5 zip.
        media = single_media_member(
            index_html, node_dict["index_file"], node_dict.get("files") or []
        )
        if not media:
            return _PendingLeaf(node_dict)
        media_path = contained_path(package.directory, media)
        if media_path is None:
            LOGGER.warning(
                "IMSCP: skipping resource %s, media path escapes package: %s",
                source_id,
                media,
            )
            return None
        return self._leaf_from_pipeline(node_dict, media_path, settings)

    def _seal_pending(self, pending, package, settings):
        """Move what the HTML5 leaves share into a dependency zip, then seal each leaf into its own zip."""
        pending = list(pending)
        members = {m for leaf in pending for m in package.closure(leaf.members)}
        # Download-only, before indexing: identical CDN downloads are md5-named,
        # so they dedup too. Leaf media compress at seal time.
        self._process_directory(package.directory, members=members)
        # Downloading rewrote references, so drop the cached ones.
        package = IMSCPPackage(package.directory)
        closures = {leaf: package.closure(leaf.members) for leaf in pending}
        # kolibri-zip renders a KPUB self-contained, so it keeps its assets.
        html5 = {
            leaf: (closures[leaf], leaf.entry)
            for leaf in pending
            if self._kpub_plan(package.directory, leaf.entry, closures[leaf]) is None
        }
        extractor = SharedAssetExtractor(package, html5)
        dependency = self._extract_dependency(extractor, settings)
        sealed = {}
        for leaf in pending:
            shared = extractor.shared(leaf) if dependency else set()
            own = [m for m in closures[leaf] if m not in shared]
            # Denested as the HTML5 handler would, so refs count ../ from the
            # paths the leaf zip will hold.
            root = find_common_root(own)
            paths = {m: m[len(root) + 1 :] if root else m for m in own}
            with tempfile.TemporaryDirectory() as directory:
                package.copy(paths, directory)
                references = dependency is not None and extractor.rewrite(
                    leaf, directory, paths, dependency["filename"]
                )
                sealed[leaf] = self._seal_leaf(
                    leaf,
                    directory,
                    {
                        **settings,
                        "entry": paths[leaf.entry],
                        "preserve_kind": leaf in html5,
                    },
                    extra_files=[dependency] if references else (),
                )
        return sealed

    def _extract_dependency(self, extractor, settings):
        """Store what ``extractor``'s leaves share as one dependency zip; its file dict, or None."""
        with tempfile.TemporaryDirectory() as dep_dir:
            if not extractor.select(dep_dir):
                return None
            try:
                self._process_directory(dep_dir, **settings)
            except (InvalidFileException, ExpectedFileException) as e:
                # Leaves stage their own copies instead.
                LOGGER.warning(
                    "IMSCP: not sharing assets, could not process them: %s", e
                )
                return None
            zip_path = create_predictable_zip(dep_dir)
        try:
            filename = copy_file_to_storage(zip_path, ext=file_formats.HTML5)
        finally:
            os.unlink(zip_path)
        return FileMetadata(
            filename=filename,
            path=config.get_storage_path(filename),
            preset=format_presets.HTML5_DEPENDENCY_ZIP,
        ).to_dict()

    def _seal_leaf(self, leaf, directory, context, extra_files):
        """Zip ``directory`` and process it as HTML5, which may promote it to a KPUB."""
        zip_path = create_predictable_zip(directory)
        try:
            return self._leaf_from_pipeline(
                leaf.node_dict, zip_path, context, extra_files
            )
        finally:
            os.unlink(zip_path)

    def _leaf_from_pipeline(self, node_dict, path, context=None, extra_files=()):
        """The leaf ``path`` backs, or ``None`` to drop just that leaf and keep decomposing."""
        source_id = node_dict.get("source_id")
        try:
            sub = self.get_pipeline().execute(path, context=context)
        except (InvalidFileException, ExpectedFileException) as e:
            LOGGER.warning(
                "IMSCP: skipping resource %s, could not process: %s", source_id, e
            )
            return None
        if not sub:
            LOGGER.warning("IMSCP: skipping resource %s, produced no files", source_id)
            return None

        kind, files, extra_fields = _summarize_leaf(sub)
        if kind is None:
            # The tree expander reads a kind-less leaf as an empty folder, so
            # drop it loudly instead.
            LOGGER.warning(
                "IMSCP: skipping resource %s, no content kind could be inferred",
                source_id,
            )
            return None

        leaf = {
            **node_content_fields(node_dict),
            "kind": kind,
            "files": files + list(extra_files),
        }
        if extra_fields:
            leaf["extra_fields"] = extra_fields
        return leaf


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
