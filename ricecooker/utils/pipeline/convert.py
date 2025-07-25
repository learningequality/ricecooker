"""
To avoid making the pipeline overly convoluted, these handlers
both validate and convert files.
"""
import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import field
from functools import partial
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

from .file_handler import ExtensionMatchingHandler
from .file_handler import StageHandler
from ricecooker import config
from ricecooker.exceptions import UnknownFileTypeError
from ricecooker.utils.audio import AudioCompressionError
from ricecooker.utils.audio import compress_audio
from ricecooker.utils.caching import generate_key
from ricecooker.utils.pipeline.context import ContextMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.subtitles import build_subtitle_converter_from_file
from ricecooker.utils.subtitles import InvalidSubtitleFormatError
from ricecooker.utils.subtitles import InvalidSubtitleLanguageError
from ricecooker.utils.subtitles import LANGUAGE_CODE_UNKNOWN
from ricecooker.utils.utils import extract_path_ext
from ricecooker.utils.videos import compress_video
from ricecooker.utils.videos import validate_media_file
from ricecooker.utils.videos import VideoCompressionError
from ricecooker.utils.youtube import get_language_with_alpha2_fallback
from ricecooker.utils.zip import create_predictable_zip


CONVERTIBLE_FORMATS = {p.id: p.convertible_formats for p in format_presets.PRESETLIST}


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
            if not config.COMPRESS and not ffmpeg_settings:
                # If we're not compressing, just validate the file.
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
            if not config.COMPRESS and not ffmpeg_settings:
                # If we're not compressing, just validate the file.
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

    def get_cache_key(self, path, audio_settings=None, video_settings=None) -> str:
        if not config.COMPRESS:
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

    def handle_file(self, path, audio_settings=None, video_settings=None):
        self.validate_archive(path)

        ext = extract_path_ext(path)

        # Create partial for reading & compressing subfiles
        file_converter = partial(
            self._read_and_compress_archive_file,
            audio_settings=audio_settings,
            video_settings=video_settings,
            ext=ext,
        )
        # create_predictable_zip will iterate over subfiles, call file_converter
        processed_zip_path = create_predictable_zip(
            path, file_converter=file_converter if config.COMPRESS else None
        )

        with self.write_file(ext) as fh:
            with open(processed_zip_path, "rb") as zf:
                shutil.copyfileobj(zf, fh)

        # Clean up
        os.unlink(processed_zip_path)

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

    def _read_and_compress_archive_file(
        self, filepath, reader, audio_settings=None, video_settings=None, ext=None
    ):
        extension = extract_path_ext(filepath, default_ext=ext)

        # If it's mp4, webm, or mp3, compress it; else pass it through
        if extension in {file_formats.MP4, file_formats.WEBM, file_formats.MP3}:
            # read the original subfile bytes
            original_bytes = reader(filepath)  # read raw data from the archive
            with tempfile.NamedTemporaryFile(delete=False) as temp_in:
                temp_in.write(original_bytes)
                temp_in.flush()

            try:
                # Create a temp out for compressed result
                with tempfile.NamedTemporaryFile(
                    suffix=f".{extension}", delete=False
                ) as temp_out:
                    temp_out.close()

                    if extension == file_formats.MP3:
                        compress_audio(
                            temp_in.name,
                            temp_out.name,
                            overwrite=True,
                            **(audio_settings or {}),
                        )
                    else:
                        compress_video(
                            temp_in.name,
                            temp_out.name,
                            overwrite=True,
                            **(video_settings or {}),
                        )

                    # read the compressed bytes
                    with open(temp_out.name, "rb") as compressed_file:
                        compressed_bytes = compressed_file.read()

                return compressed_bytes
            finally:
                os.unlink(temp_in.name)
                if os.path.exists(temp_out.name):
                    os.unlink(temp_out.name)

        return reader(filepath)


class HTML5ConversionHandler(ArchiveProcessingBaseHandler):

    EXTENSIONS = {file_formats.HTML5}
    FILE_TYPE = "HTML5"

    def validate_archive(self, path: str):
        with self.open_and_verify_archive(path) as zf:
            # Check index.html exists and is valid HTML
            index_html = self.read_file_from_archive(zf, "index.html")
            try:
                dom = html5lib.parse(index_html, namespaceHTMLElements=False)
                body = dom.find("body")
                if body is None:
                    raise InvalidFileException(
                        f"File {path} is not a valid HTML5 file, index.html is missing a body element."
                    )
                # Check that the body has at least one child element
                # for some reason it seems like comments don't get a string tag attribute
                body_children = [
                    c for c in body.iter() if isinstance(c.tag, str) and c.tag != "body"
                ]
                if not body.text.strip() and not body_children:
                    raise InvalidFileException(
                        f"File {path} is not a valid HTML5 file, index.html is empty."
                    )
            except ParseError:
                raise InvalidFileException(
                    f"File {path} is not a valid HTML5 file, index.html is not well-formed."
                )


class H5PConversionHandler(ArchiveProcessingBaseHandler):

    EXTENSIONS = {file_formats.H5P}
    FILE_TYPE = "H5P"

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
                        f'File {path} is not a valid bloom file, meta.json missing required fields: {", ".join(missing_fields)}'
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
        HTML5ConversionHandler,
        VideoCompressionHandler,
        AudioCompressionHandler,
    ]
