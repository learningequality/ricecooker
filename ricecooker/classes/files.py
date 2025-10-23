import os
import tempfile
from urllib.parse import urlparse

from le_utils.constants import exercises
from le_utils.constants import file_formats
from le_utils.constants import format_presets
from le_utils.constants import languages
from requests import HTTPError

from .. import config
from ..exceptions import UnknownFileTypeError
from ricecooker.utils.caching import FILECACHE
from ricecooker.utils.caching import get_cache_filename
from ricecooker.utils.images import create_image_from_epub
from ricecooker.utils.images import create_image_from_pdf_page
from ricecooker.utils.images import create_image_from_zip
from ricecooker.utils.images import create_tiled_image
from ricecooker.utils.images import ThumbnailGenerationError
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.convert import AudioCompressionHandler
from ricecooker.utils.pipeline.convert import ImageConversionHandler
from ricecooker.utils.pipeline.convert import SubtitleConversionHandler
from ricecooker.utils.pipeline.convert import VideoCompressionHandler
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.transfer import CatchAllWebResourceDownloadHandler
from ricecooker.utils.utils import copy_file_to_storage
from ricecooker.utils.utils import extract_path_ext
from ricecooker.utils.videos import extract_thumbnail_from_video
from ricecooker.utils.youtube import get_language_with_alpha2_fallback

fallback_pipeline = FilePipeline()

# Lookup table for convertible file formats for a given preset
# used for converting avi/flv/etc. videos and srt subtitles
CONVERTIBLE_FORMATS = {p.id: p.convertible_formats for p in format_presets.PRESETLIST}


class ThumbnailPresetMixin(object):
    def get_preset(self):
        thumbnail_preset = self.node.get_thumbnail_preset()
        if thumbnail_preset is None:
            UnknownFileTypeError("Thumbnails are not supported for node kind.")
        return thumbnail_preset


class File(object):
    original_filename = None
    node = None
    error = None
    default_ext = None
    filename = None
    language = None
    assessment_item = None
    is_primary = False
    duration = None
    skip_upload = False
    default_preset = None

    def __init__(
        self,
        preset=None,
        language=None,
        default_ext=None,
        source_url=None,
        duration=None,
        original_filename=None,
        filename=None,
    ):
        self.preset = preset
        self.set_language(language)
        self.default_ext = default_ext or self.default_ext
        self.source_url = source_url
        self.duration = duration
        self.original_filename = original_filename
        self.filename = filename

    def set_language(self, language):
        """Set self.language to internal lang. repr. code from str or Language object."""
        if isinstance(language, str):
            language_obj = languages.getlang(language)
            if language_obj:
                self.language = language_obj.code
            else:
                raise TypeError("Language code {} not found".format(language))
        if isinstance(language, languages.Language):
            self.language = language.code

    def validate(self):
        pass

    def get_preset(self):
        if self.preset:
            return self.preset
        if self.default_preset:
            return self.default_preset
        raise NotImplementedError(
            f"preset must be set if preset and default_preset isn't specified when creating {self.__class__.__name__} "
            f"object for file {self.filename} ({self.original_filename})"
        )

    def get_filename(self):
        return self.filename or self.process_file()

    @property
    def checksum(self):
        return self.get_filename().split(".")[0]

    @property
    def extension(self):
        return self.get_filename().split(".")[1]

    @property
    def size(self):
        return os.path.getsize(config.get_storage_path(self.get_filename()))

    def truncate_fields(self):
        if (
            self.original_filename
            and len(self.original_filename) > config.MAX_ORIGINAL_FILENAME_LENGTH
        ):
            config.print_truncate(
                "original_filename", self.node.source_id, self.original_filename
            )
            original_extension = self.original_filename.split(".")[-1]
            if original_extension == self.original_filename:
                original_extension = ""
            self.original_filename = self.original_filename.split(".")[0]
            extension_length = (
                0 if not original_extension else len(original_extension) + 1
            )
            self.original_filename = self.original_filename[
                : config.MAX_ORIGINAL_FILENAME_LENGTH - extension_length
            ]
            if original_extension:
                self.original_filename += "." + original_extension

        if self.source_url and len(self.source_url) > config.MAX_SOURCE_URL_LENGTH:
            config.print_truncate(
                "file_source_url", self.node.source_id, self.source_url
            )
            self.source_url = self.source_url[: config.MAX_SOURCE_URL_LENGTH]

    def file_dict(self, filename=None):
        if not filename:
            filename = self.get_filename()
        return {
            "size": self.size,
            "preset": self.get_preset(),
            "filename": filename,
            "original_filename": self.original_filename,
            "language": self.language,
            "source_url": self.source_url,
            "duration": self.duration,
        }

    def to_dict(self):
        filename = self.get_filename()

        # If file was successfully downloaded, return dict
        # Otherwise return None
        if filename:
            if os.path.isfile(config.get_storage_path(filename)):
                return self.file_dict(filename=filename)
            else:
                config.LOGGER.warning(
                    "File not found: {}".format(config.get_storage_path(filename))
                )

        return None

    def process_file(self):
        return self.filename


class DownloadFile(File):
    ext = None
    allowed_formats = None

    def __init__(self, path, context=None, **kwargs):
        self.path = path.strip()
        self.context = {
            "default_ext": self.default_ext,
        }
        self.context.update(context or {})
        super(DownloadFile, self).__init__(**kwargs)

    def validate(self):
        """
        Ensure `self.path` has one of the extensions in `self._allowed_formats`.
        """
        assert self.path, "{} must have a path".format(self.__class__.__name__)
        extension = self.ext
        if not extension:
            extension = extract_path_ext(self.path, default_ext=self.default_ext)
        if self.allowed_formats is not None and extension not in self.allowed_formats:
            raise ValueError(
                f"Incompatible extension {extension} for {self.__class__.__name__} at {self.path}"
            )

    def __str__(self):
        return self.path

    def process_file(self):
        try:
            try:
                self.validate()
            except ValueError as ve:
                raise InvalidFileException from ve
            pipeline = config.FILE_PIPELINE or fallback_pipeline
            metadata = pipeline.execute(
                self.path, context=self.context, skip_cache=config.UPDATE
            )[0]
            metadata = metadata.to_dict()
            for key in metadata:
                if key == "path":
                    # Don't overwrite the input path.
                    continue
                setattr(self, key, metadata[key])
            self.validate()
            if not self.filename:
                raise InvalidFileException("File could not be processed by pipeline")
            return super().process_file()
        except (ExpectedFileException, InvalidFileException) as err:
            self.error = str(err)
            config.LOGGER.debug("Failed to download, error is: {}".format(err))
            config.FAILED_FILES.append(self)
            return None


class ImageDownloadFile(DownloadFile):
    allowed_formats = ImageConversionHandler.EXTENSIONS | {file_formats.SVG}


class SlideImageFile(ImageDownloadFile):
    default_ext = file_formats.PNG
    is_primary = True
    default_preset = format_presets.SLIDESHOW_IMAGE

    def __init__(self, path, caption="", descriptive_text="", **kwargs):
        self.caption = caption
        self.descriptive_text = descriptive_text
        super(ImageDownloadFile, self).__init__(path, **kwargs)


class ThumbnailFile(ThumbnailPresetMixin, ImageDownloadFile):
    default_ext = file_formats.PNG


class AudioFile(DownloadFile):
    default_ext = file_formats.MP3
    allowed_formats = AudioCompressionHandler.EXTENSIONS
    is_primary = True
    default_preset = format_presets.AUDIO

    def __init__(self, path, ffmpeg_settings=None, **kwargs):
        super(AudioFile, self).__init__(
            path, context={"audio_settings": ffmpeg_settings or {}}, **kwargs
        )


class DocumentFile(DownloadFile):
    default_ext = file_formats.PDF
    allowed_formats = {file_formats.PDF}
    is_primary = True
    default_preset = format_presets.DOCUMENT


class EPubFile(DownloadFile):
    default_ext = file_formats.EPUB
    allowed_formats = {file_formats.EPUB}
    is_primary = True
    default_preset = format_presets.EPUB


class BloomPubFile(DownloadFile):
    default_ext = file_formats.BLOOMPUB
    allowed_formats = {file_formats.BLOOMPUB, file_formats.BLOOMD}
    is_primary = True
    default_preset = format_presets.BLOOMPUB


class HTMLZipFile(DownloadFile):
    default_ext = file_formats.HTML5
    allowed_formats = {file_formats.HTML5}
    is_primary = True
    default_preset = format_presets.HTML5_ZIP


class H5PFile(DownloadFile):
    default_ext = file_formats.H5P
    allowed_formats = {file_formats.H5P}
    is_primary = True
    default_preset = format_presets.H5P_ZIP


class VideoFile(DownloadFile):
    default_ext = file_formats.MP4
    allowed_formats = VideoCompressionHandler.EXTENSIONS
    is_primary = True

    def __init__(self, path, ffmpeg_settings=None, **kwargs):
        super(VideoFile, self).__init__(
            path, context={"video_settings": ffmpeg_settings or {}}, **kwargs
        )


class WebVideoFile(DownloadFile):
    is_primary = True
    default_ext = file_formats.MP4

    def __init__(
        self,
        web_url,
        download_settings=None,
        high_resolution=False,
        maxheight=None,
        **kwargs,
    ):
        super(WebVideoFile, self).__init__(web_url, **kwargs)
        if download_settings:
            self.context["yt_dlp_settings"] = download_settings
        if maxheight:
            self.context["max_height"] = maxheight
        self.context["high_resolution"] = high_resolution


class YouTubeVideoFile(WebVideoFile):
    def __init__(self, youtube_id, **kwargs):
        super(YouTubeVideoFile, self).__init__(
            "http://www.youtube.com/watch?v={}".format(youtube_id), **kwargs
        )


class YouTubeSubtitleFile(File):
    default_preset = format_presets.VIDEO_SUBTITLE
    """
    Helper class for downloading youtube subtitles.
    Args:
       youtube_id (string): YouTube ID of video (required)
       language (string): internal language id format `{primary_code}` or `{primary_code}-{subcode}` (required) \
                          alternatively, you can provide the language code recognized by YouTube.
    Use the helper method `is_youtube_subtitle_file_supported_language` to check
    if `language` is a supported code before creating the `YouTubeSubtitleFile`.
    """

    def __init__(self, youtube_id, language=None, **kwargs):
        self.youtube_url = "http://www.youtube.com/watch?v={}".format(youtube_id)
        if isinstance(language, languages.Language):
            language = language.code
        self.youtube_language = (
            language  # save youtube language code (can differ from internal repr.)
        )
        language_obj = get_language_with_alpha2_fallback(language)
        super(YouTubeSubtitleFile, self).__init__(language=language_obj.code, **kwargs)
        self.context = {
            "subtitle_languages": [self.youtube_language],
            "download_video": False,
        }
        assert self.language, "Subtitles must have a language"


class SubtitleFile(DownloadFile):
    default_ext = file_formats.VTT
    allowed_formats = SubtitleConversionHandler.EXTENSIONS
    default_preset = format_presets.VIDEO_SUBTITLE

    def __init__(self, path, **kwargs):
        """
        If `subtitlesformat` arg is empty, then type will be detected and converted if supported
        """
        self.subtitlesformat = kwargs.get("subtitlesformat", None)
        self.ext = self.subtitlesformat
        if "subtitlesformat" in kwargs:
            del kwargs["subtitlesformat"]
        super(SubtitleFile, self).__init__(path, **kwargs)
        assert self.language, "Subtitles must have a language"
        self.context = {
            "language": self.language,
            "subtitle_format": self.subtitlesformat,
            "default_ext": self.subtitlesformat,
        }


class Base64ImageFile(ThumbnailPresetMixin, DownloadFile):
    default_ext = file_formats.PNG

    def __init__(self, encoding, **kwargs):
        super().__init__(encoding, **kwargs)


class _ExerciseBase64ImageFile(Base64ImageFile):
    default_preset = format_presets.EXERCISE_IMAGE

    def get_replacement_str(self):
        return self.get_filename() or self.path


class _ExerciseImageFile(ImageDownloadFile):
    default_preset = format_presets.EXERCISE_IMAGE

    def get_replacement_str(self):
        return self.get_filename() or self.path


class _ExerciseGraphieFile(File):
    default_ext = file_formats.GRAPHIE
    default_preset = format_presets.EXERCISE_GRAPHIE

    def __init__(self, path, ka_language, **kwargs):
        super().__init__(**kwargs)
        self.original_filename = path.split("/")[-1].split(".")[0]
        self.path = path
        self.ka_language = ka_language

    def validate(self):
        try:
            parsed_url = urlparse(self.path)
            if not parsed_url.scheme == "http" and not parsed_url.scheme == "https":
                raise ValueError("Invalid URL")
        except ValueError:
            raise ValueError("_ExerciseGraphieFile must have a valid URL")

    def get_replacement_str(self):
        if "http" in self.path:
            return self.path.split("/")[-1].split(".")[0] or self.path
        else:
            return self.path.split(os.path.sep)[-1].split(".")[0] or self.path

    def process_file(self):
        """download: download a web+graphie file
        Args: None
        Returns: None
        """
        try:
            self.filename = self.generate_graphie_file()
            config.LOGGER.info("\t--- Generated graphie {}".format(self.filename))
            return self.filename
        # Catch errors related to reading file path and handle silently
        except tuple(CatchAllWebResourceDownloadHandler.HANDLED_EXCEPTIONS) as err:
            self.error = str(err)
            config.FAILED_FILES.append(self)

    def generate_graphie_file(self):
        if self.ka_language is None:
            raise ValueError("ka_language must be specified")
        key = "GRAPHIE: {}".format(
            self.path + (self.ka_language if self.ka_language != "en" else "")
        )

        cache_file = get_cache_filename(key)
        if not config.UPDATE and cache_file:
            return cache_file

        tempf = tempfile.NamedTemporaryFile(
            suffix=".{}".format(file_formats.GRAPHIE), delete=False
        )
        # Initialize hash and files
        delimiter = bytes(exercises.GRAPHIE_DELIMITER, "UTF-8")
        config.LOGGER.info("\tDownloading graphie {}".format(self.original_filename))
        # Write to graphie file
        r = config.DOWNLOAD_SESSION.get(self.path + ".svg", stream=True)
        r.raise_for_status()
        for chunk in r.iter_content():
            tempf.write(chunk)
        tempf.write(delimiter)
        # Separate the path into these components, splitting on the final /
        # in the same way that the KA frontend code does for localization here:
        # https://github.com/Khan/perseus/blob/458d3ed600be91dd75a30a80bfac1fbd87c60bcd/packages/perseus/src/util/graphie-utils.ts#L75
        if self.ka_language == "en":
            json_path_base = self.path
        else:
            base_path, _, file_hash = self.path.rpartition("/")
            json_path_base = base_path + "/" + self.ka_language + "/" + file_hash
        should_cache = True
        try:
            r = config.DOWNLOAD_SESSION.get(json_path_base + "-data.json", stream=True)
            r.raise_for_status()
        except HTTPError:
            if self.ka_language == "en":
                raise
            r = config.DOWNLOAD_SESSION.get(self.path + "-data.json", stream=True)
            r.raise_for_status()
            should_cache = False
        for chunk in r.iter_content():
            tempf.write(chunk)
        tempf.close()
        filename = copy_file_to_storage(tempf.name, ext=file_formats.GRAPHIE)
        os.unlink(tempf.name)
        if should_cache:
            FILECACHE.set(key, bytes(filename, "utf-8"))
        return filename


# EXTRACTED THUMBNAILS
################################################################################


class ExtractedThumbnailFile(ThumbnailFile):
    extractor_kwargs = {}  # subclass can specify additional options

    def process_file(self):
        """
        Generate the thumbnail from source file in `self.path` by calling the
        ``extractor_fun`` method of the subclass.
        Returns: filename or None
        """
        config.LOGGER.info("\t--- Extracting thumbnail from {}".format(self.path))
        tempf = tempfile.NamedTemporaryFile(
            suffix=".{}".format(file_formats.PNG), delete=False
        )
        tempf.close()
        try:
            self.extractor_fun(self.path, tempf.name, **self.extractor_kwargs)
            filename = copy_file_to_storage(tempf.name, ext=file_formats.PNG)
            os.unlink(tempf.name)
            config.LOGGER.info("\t--- Extracted thumbnail {}".format(filename))
            self.filename = filename
        except ThumbnailGenerationError as err:
            config.LOGGER.warning("\t    Failed to extract thumbnail {}".format(err))
            self.filename = None
            self.error = str(err)
            config.FAILED_FILES.append(self)
        return self.filename

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        """
        The function in the subclass that performs the thumbnail generation.
        Args:
            fpath_in: the local path of the source file
            thumbpath_out: the destination path to write thumbnail to (temp file)
            **kwargs: any additional class-specific arguments passed in
        """
        raise NotImplementedError("The subclass must implement this method.")


class ExtractedPdfThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {"page_number": 0, "crop": None}
    allowed_formats = DocumentFile.allowed_formats

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_image_from_pdf_page(fpath_in, thumbpath_out, **kwargs)


class ExtractedEPubThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {"crop": None}
    allowed_formats = EPubFile.allowed_formats

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_image_from_epub(fpath_in, thumbpath_out, **kwargs)


class ExtractedHTMLZipThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {"crop": "smart"}
    allowed_formats = HTMLZipFile.allowed_formats

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_image_from_zip(fpath_in, thumbpath_out, **kwargs)


class ExtractedVideoThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {"overwrite": True}
    allowed_formats = VideoFile.allowed_formats

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        extract_thumbnail_from_video(fpath_in, thumbpath_out, **kwargs)


class TiledThumbnailFile(ThumbnailPresetMixin, File):
    allowed_formats = [file_formats.JPG, file_formats.JPEG, file_formats.PNG]

    def __init__(self, source_nodes, **kwargs):
        self.sources = []
        for n in source_nodes:
            images = [
                f for f in n.files if isinstance(f, ThumbnailFile) and f.get_filename()
            ]
            if len(images) > 0:
                self.sources.append(images[0])
        super(TiledThumbnailFile, self).__init__(**kwargs)

    def process_file(self):
        self.filename = self.generate_tiled_image()
        config.LOGGER.info("\t--- Tiled image {}".format(self.filename))
        return self.filename

    def generate_tiled_image(self):
        num_pictures = 0
        if len(self.sources) >= 4:
            num_pictures = 4
        elif len(self.sources) >= 1:
            num_pictures = 1
        else:
            return None
        config.LOGGER.info("\tGenerating tiled thumbnail.")
        images = [
            config.get_storage_path(f.get_filename())
            for f in self.sources[:num_pictures]
        ]
        with tempfile.NamedTemporaryFile(
            suffix=".{}".format(file_formats.PNG)
        ) as tempf:
            tempf.close()
            create_tiled_image(images, tempf.name)
            filename = copy_file_to_storage(tempf.name, ext=file_formats.PNG)
            return filename


class StudioFile(File):
    """
    Reuse a file that we already know to exist on the remote (Studio).
    This allows for channels to be updated without having to redownload all files again.
    """

    skip_upload = True
    size = None

    def __init__(self, checksum, ext, preset, is_primary=False, **kwargs):
        kwargs["preset"] = preset
        super(StudioFile, self).__init__(**kwargs)
        self._validated = False
        self.filename = "{}.{}".format(checksum, ext)
        self.is_primary = is_primary

    def validate(self):
        if not self._validated:
            file_url = config.get_storage_url(self.filename)
            response = config.DOWNLOAD_SESSION.head(file_url)
            try:
                response.raise_for_status()
            except Exception as e:
                raise ValueError(
                    "Could not find remote file {} for reason {}".format(
                        self.filename, e
                    )
                )
            self.size = int(response.headers.get("Content-Length", 0))
            self._validated = True

    def to_dict(self):
        return self.file_dict()

    def __str__(self):
        return self.filename


# add alias for back-compatibility
RemoteFile = StudioFile
