# Node models to represent channel's tree
from __future__ import unicode_literals

from cachecontrol.caches.file_cache import FileCache
import hashlib
import os
from PIL import Image
import json
import requests
from requests.exceptions import MissingSchema, HTTPError, ConnectionError, InvalidURL, InvalidSchema
import shutil
from subprocess import CalledProcessError
import tempfile
import youtube_dl
import zipfile

from urllib.parse import urlparse

from le_utils.constants import languages
from le_utils.constants import file_formats, format_presets, exercises
from pressurecooker.encodings import get_base64_encoding, write_base64_to_file
from pressurecooker.images import create_image_from_pdf_page
from pressurecooker.images import create_image_from_epub
from pressurecooker.images import create_image_from_zip
from pressurecooker.videos import extract_thumbnail_from_video
from pressurecooker.images import create_waveform_image
from pressurecooker.images import create_tiled_image
from pressurecooker.images import ThumbnailGenerationError
from pressurecooker.subtitles import build_subtitle_converter_from_file
from pressurecooker.subtitles import LANGUAGE_CODE_UNKNOWN
from pressurecooker.subtitles import InvalidSubtitleFormatError, InvalidSubtitleLanguageError
from pressurecooker.videos import guess_video_preset_by_resolution, compress_video, VideoCompressionError
from pressurecooker.youtube import YouTubeResource

from .. import config
from ..exceptions import UnknownFileTypeError

# Cache for filenames
FILECACHE = FileCache(config.FILECACHE_DIRECTORY, use_dir_lock=True, forever=True)
HTTP_CAUGHT_EXCEPTIONS = (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError, AssertionError)

# Lookup table for convertible file formats for a given preset
# used for converting avi/flv/etc. videos and srt subtitles
CONVERTIBLE_FORMATS = {p.id: p.convertible_formats for p in format_presets.PRESETLIST}


def extract_path_ext(path, default_ext=None):
    """
    Extract file extension (without dot) from `path` or return `default_ext` if
    path does not contain a valid extension.
    """
    _, dotext = os.path.splitext(path)
    if dotext:
        ext = dotext[1:]
        if len(ext) > 3 and '?' in ext:   # strip off any querystring if present
            ext = ext.split('?')[0]
    else:
        ext = None
    if not ext and default_ext:
        ext = default_ext
    if not ext:
        raise ValueError('No extension in path {} and default_ext is None'.format(path))
    return ext.lower()


def generate_key(action, path_or_id, settings=None, default=" (default)"):
    """ generate_key: generate key used for caching
        Args:
            action (str): how video is being processed (e.g. COMPRESSED or DOWNLOADED)
            path_or_id (str): path to video or youtube_id
            settings (dict): settings for compression or downloading passed in by user
            default (str): if settings are None, default to this extension (avoid overwriting keys)
        Returns: filename
    """
    if settings and 'postprocessors' in settings:
        # get determinisic dict serialization for nested dicts under Python 3.5
        settings_str = json.dumps(settings, sort_keys=True)
    else:
        # keep using old strategy to avoid invalidating all chef caches
        settings_str = "{}".format(str(sorted(settings.items()))) if settings else default
    return "{}: {} {}".format(action.upper(), path_or_id, settings_str)


def get_cache_filename(key):
    cache_file = FILECACHE.get(key)
    if cache_file:
        cache_file = cache_file.decode('utf-8')
        # if the file was somehow deleted, make sure we don't return it.
        if not os.path.exists(config.get_storage_path(cache_file)):
            cache_file = None
    return cache_file


def cache_is_outdated(path, cache_file):
    outdated = True
    if not cache_file:
        return True

    if is_valid_url(path):
        # Downloading is expensive, so always use cache if we don't explicitly try to update.
        outdated = False
    else:
        # check if the on disk file has changed
        cache_hash = get_hash(path)
        outdated = not cache_hash or not cache_file.startswith(cache_hash)

    return outdated


def download(path, default_ext=None):
    """
    Download `path` and save to storage based on file extension derived from `path`.
    :param path: An URL or a local path
    :param default_ext: fallback ext for file when path does not end with .ext
    :return: filename derived from hash of file contents {md5hash(file)}.ext
    :rtype: sting (path of the form `{md5hash(file at path)}.ext`
    """
    key = "DOWNLOAD:{}".format(path)

    cache_file = get_cache_filename(key)
    if not config.UPDATE and not cache_is_outdated(path, cache_file):
        config.LOGGER.info("\tUsing cached file for: {}".format(path))
        return cache_file

    config.LOGGER.info("\tDownloading {}".format(path))
    # Write file to temporary file
    with tempfile.TemporaryFile() as tempf:
        hash = write_and_get_hash(path, tempf)
        tempf.seek(0)
        # Get extension of file or use `default_ext` if none found
        ext = extract_path_ext(path, default_ext=default_ext)
        filename = '{0}.{ext}'.format(hash.hexdigest(), ext=ext)
        copy_file_to_storage(filename, tempf)
        FILECACHE.set(key, bytes(filename, "utf-8"))
        config.LOGGER.info("\t--- Downloaded {}".format(filename))

    return filename


def download_and_convert_video(path, default_ext=file_formats.MP4, ffmpeg_settings=None):
    """
    Auto-converting variant of download function that handles all video formats.
    """
    ffmpeg_settings = ffmpeg_settings or {}
    key = "DOWNLOAD:{}".format(path)
    cache_file = get_cache_filename(key)
    if is_valid_url(path) and not config.UPDATE and cache_file:
        return cache_file

    config.LOGGER.info("\tDownloading {}".format(path))

    # Get extension of convertible video file
    ext = extract_path_ext(path)
    converted_path = None

    # Convert video to temporary file
    with tempfile.NamedTemporaryFile(suffix=".{}".format(ext), delete=False) as tempf:
        # Write unsupported video to temporary file
        write_and_get_hash(path, tempf)
        tempf.seek(0)
        # Compress video into mp4 file
        path, _ext = os.path.splitext(tempf.name)
        converted_path = "{}.{}".format(path, file_formats.MP4)
        tempf.close()
        compress_video(tempf.name, converted_path, overwrite=True, **ffmpeg_settings)
        os.unlink(tempf.name)

    # Write converted file to another temporary file
    with tempfile.TemporaryFile() as tempf2:
        hash = write_and_get_hash(converted_path, tempf2)
        tempf2.seek(0)
        filename = '{0}.{ext}'.format(hash.hexdigest(), ext=file_formats.MP4)
        copy_file_to_storage(filename, tempf2)
        os.unlink(converted_path)
        FILECACHE.set(key, bytes(filename, "utf-8"))
        return filename


def is_valid_url(path):
    """
    Return `True` if path is a valid URL, else `False` if path is a local path.
    """
    parts = urlparse(path)
    return parts.scheme != '' and parts.netloc != ''


def write_and_get_hash(path, write_to_file, hash=None):
    """
    Download file at `path` and write its contents to the file `write_to_file`.
    First check if `path` is a URL and if so perform a GET request for the path,
    otherwise try to access `path` on the local filesystem.

    :param path: An URL or a local filepath
    :type path: str
    :param write_to_file: Desrination file to which we write the contents of path.
    :type write_to_file: file
    :param hash:  initial hasher state (used when writing multiple paths to the same file (.graphie)
    :type hash: hashlib hasher (optional)
    :return: updated hasher state
    :rtype: hashlib hasher (updated)
    """
    hash = hash or hashlib.md5()  # start hasher if an existing one not provided
    if is_valid_url(path):
        # CASE A: path is a URL (http://, https://, or file://, etc.)
        r = config.DOWNLOAD_SESSION.get(path, stream=True)
        r.raise_for_status()
        for chunk in r:
            write_to_file.write(chunk)
            hash.update(chunk)
    else:
        # CASE B: path points to a local filesystem file
        with open(path, 'rb') as fobj:
            for chunk in iter(lambda: fobj.read(2097152), b""):
                write_to_file.write(chunk)
                hash.update(chunk)
    assert write_to_file.tell() > 0, "File failed to write (corrupted)."
    return hash


def copy_file_to_storage(filename, srcfile, delete_original=False):
    """
    Copy `srcfile` (file of path) to desrination storage path for `filename`,
    of the form `storage/f/i/filename.ext` when filename is `filename.ext`.
    :rtype: None
    """
    # Some files might have been closed, so only filepath will work
    if isinstance(srcfile, str):
        srcfile = open(srcfile, 'rb')

    # Write file to local storage
    with open(config.get_storage_path(filename), 'wb') as destf:
        if delete_original:
            shutil.move(srcfile.name, destf.name)
        else:
            shutil.copyfileobj(srcfile, destf)


def get_hash(filepath):
    file_hash = hashlib.md5()
    with open(filepath, 'rb') as fobj:
        for chunk in iter(lambda: fobj.read(2097152), b""):
            file_hash.update(chunk)
    return file_hash.hexdigest()


def compress_video_file(filename, ffmpeg_settings):
    """
    Calls the pressurecooker function `compress_video` to compress filename (source)
    stored in storage. Returns the filename of the compressed file.
    """
    ffmpeg_settings = ffmpeg_settings or {}
    key = generate_key("COMPRESSED", filename, settings=ffmpeg_settings, default=" (default compression)")

    cache_file = get_cache_filename(key)
    if not config.UPDATE and cache_file:
        return cache_file

    config.LOGGER.info("\t--- Compressing {}".format(filename))

    tempf = tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.MP4), delete=False)
    tempf.close() # Need to close so pressure cooker can write to file
    compress_video(config.get_storage_path(filename), tempf.name, overwrite=True, **ffmpeg_settings)
    compressedfilename = "{}.{}".format(get_hash(tempf.name), file_formats.MP4)

    copy_file_to_storage(compressedfilename, tempf.name)
    os.unlink(tempf.name)
    FILECACHE.set(key, bytes(compressedfilename, "utf-8"))
    return compressedfilename


def download_from_web(web_url, download_settings, file_format=file_formats.MP4, ext="", download_ext=""):
    """
    Download `web_url` using YoutubeDL using `download_settings` options.
    Args:
        download_settings (dict): options to pass onto YoutubeDL
        file_format (str): one of "mp4" or "vtt"
        ext (str): extensions to use as part of `outtmpl` given to YoutubeDL
        download_ext (str): extensions to append to `outtmpl` after downloading
    This is function operates differently when downloadin videos and substitles.
    For videos we set the `outtmpl` to the actual filename that will be downloaded,
    and the function must be called with ext = ".mp4" and download_ext="".
    For subtitles we set the `outtmpl` to extension-less string, and YoutubeDL
    automatically appends the language code and vtt extension, so the function
    must be called with ext="" and download_ext=".{youtube_lang}.vtt"
    :return: filename derived from hash of file contents {md5hash(file)}.ext
    """
    key = generate_key("DOWNLOADED", web_url, settings=download_settings)
    cache_file = get_cache_filename(key)
    if cache_file:
        return cache_file

    # Get hash of web_url to act as temporary storage name
    url_hash = hashlib.md5()
    url_hash.update(web_url.encode('utf-8'))
    tempfilename = "{}{ext}".format(url_hash.hexdigest(), ext=ext)
    outtmpl_path = os.path.join(tempfile.gettempdir(), tempfilename)
    download_settings["outtmpl"] = outtmpl_path
    destination_path = outtmpl_path + download_ext  # file dest. after download

    # Delete files in case previously downloaeded
    if os.path.exists(outtmpl_path):
        os.remove(outtmpl_path)
    if os.path.exists(destination_path):
        os.remove(destination_path)

    # Download the web_url which can be either a video or subtitles
    if not config.USEPROXY:
        # Connect to YouTube directly
        with youtube_dl.YoutubeDL(download_settings) as ydl:
            ydl.download([web_url])
            if not os.path.exists(destination_path):
                raise youtube_dl.utils.DownloadError('Failed to download ' + web_url)
    else:
        # Connect to YouTube via an HTTP proxy
        yt_resource = YouTubeResource(web_url, useproxy=True, options=download_settings)
        result1 = yt_resource.get_resource_info()
        if result1 is None:
            raise youtube_dl.utils.DownloadError('Failed to get resource info')
        download_settings["writethumbnail"] = False  # overwrite default behaviour
        if file_format == file_formats.VTT:
            # We need to use the proxy when downloading subtitles
            result2 = yt_resource.download(options=download_settings, useproxy=True)
        else:
            # For video files we can skip the proxy for faster download speed
            result2 = yt_resource.download(options=download_settings)
        if result2 is None or not os.path.exists(destination_path):
            raise youtube_dl.utils.DownloadError('Failed to download resource ' + web_url)

    # Write file to local storage
    filename = "{}.{}".format(get_hash(destination_path), file_format)
    with open(destination_path, "rb") as dlf, open(config.get_storage_path(filename), 'wb') as destf:
        shutil.copyfileobj(dlf, destf)

    FILECACHE.set(key, bytes(filename, "utf-8"))
    return filename


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

    def __init__(self, preset=None, language=None, default_ext=None, source_url=None):
        self.preset = preset
        self.set_language(language)
        self.default_ext = default_ext or self.default_ext
        self.source_url = source_url

    def set_language(self, language):
        """ Set self.language to internal lang. repr. code from str or Language object. """
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
        raise NotImplementedError("preset must be set if preset isn't specified when creating File object")

    def get_filename(self):
        return self.filename or self.process_file()

    def truncate_fields(self):
        if self.original_filename and len(self.original_filename) > config.MAX_ORIGINAL_FILENAME_LENGTH:
            config.print_truncate("original_filename", self.node.source_id, self.original_filename)
            self.original_filename = self.original_filename[:config.MAX_ORIGINAL_FILENAME_LENGTH]

        if self.source_url and len(self.source_url) > config.MAX_SOURCE_URL_LENGTH:
            config.print_truncate("file_source_url", self.node.source_id, self.source_url)
            self.source_url = self.source_url[:config.MAX_SOURCE_URL_LENGTH]

    def to_dict(self):
        filename = self.get_filename()

        # If file was successfully downloaded, return dict
        # Otherwise return None
        if filename:
            if os.path.isfile(config.get_storage_path(filename)):
                return {
                    'size': os.path.getsize(config.get_storage_path(filename)),
                    'preset': self.get_preset(),
                    'filename': filename,
                    'original_filename': self.original_filename,
                    'language': self.language,
                    'source_url': self.source_url,
                }
            else:
                config.LOGGER.warning("File not found: {}".format(config.get_storage_path(filename)))

        return None

    def process_file(self):
        # Overwrite in subclasses
        pass


class DownloadFile(File):
    allowed_formats = []

    def __init__(self, path, **kwargs):
        self.path = path.strip()
        super(DownloadFile, self).__init__(**kwargs)

    def validate(self):
        """
        Ensure `self.path` has one of the extensions in `self.allowed_formats`.
        """
        assert self.path, "{} must have a path".format(self.__class__.__name__)
        ext = extract_path_ext(self.path, default_ext=self.default_ext)
        # don't validate for single-digit extension, or no extension
        if len(ext) > 1:
            assert ext in self.allowed_formats, "{} must have one of the " \
                "following extensions: {} (instead, got '{}' from '{}')".format(
                    self.__class__.__name__, self.allowed_formats, ext, self.path)

    def process_file(self):
        try:
            self.filename = download(self.path, default_ext=self.default_ext)
            return self.filename
        # Catch errors related to reading file path and handle silently
        except HTTP_CAUGHT_EXCEPTIONS as err:
            self.error = err
            config.LOGGER.debug("Failed to download, error is: {}".format(err))
            config.FAILED_FILES.append(self)
            return None

    def __str__(self):
        return self.path


class SlideImageFile(DownloadFile):
    default_ext = file_formats.PNG
    allowed_formats = [file_formats.JPG, file_formats.JPEG, file_formats.PNG]
    is_primary = True

    def __init__(self, path, caption="", descriptive_text="", **kwargs):
        self.caption = caption
        self.descriptive_text = descriptive_text
        self.path = path.strip()
        super(DownloadFile, self).__init__(**kwargs)

    def get_preset(self):
        return format_presets.SLIDESHOW_IMAGE


class ThumbnailFile(ThumbnailPresetMixin, DownloadFile):
    default_ext = file_formats.PNG
    allowed_formats = [file_formats.JPG, file_formats.JPEG, file_formats.PNG]

    def process_file(self):
        """
        Call DownloadFile's `process_file` and ensure the result is a valid img.
        """
        self.filename = super(ThumbnailFile, self).process_file()
        if self.filename:
            try:
                image_path = config.get_storage_path(self.filename)
                img = Image.open(image_path)
                img.verify()
            except IOError as e:       # Catch invalid or broken thumbnail files
                self.filename = None
                self.error = e
                config.FAILED_FILES.append(self)
        return self.filename


class AudioFile(DownloadFile):
    default_ext = file_formats.MP3
    allowed_formats = [file_formats.MP3]
    is_primary = True

    def get_preset(self):
        return self.preset or format_presets.AUDIO


class DocumentFile(DownloadFile):
    default_ext = file_formats.PDF
    allowed_formats = [file_formats.PDF]
    is_primary = True

    def get_preset(self):
        return self.preset or format_presets.DOCUMENT


class EPubFile(DownloadFile):
    default_ext = file_formats.EPUB
    allowed_formats = [file_formats.EPUB]
    is_primary = True

    def get_preset(self):
        return self.preset or format_presets.EPUB


class HTMLZipFile(DownloadFile):
    default_ext = file_formats.HTML5
    allowed_formats = [file_formats.HTML5]
    is_primary = True

    def get_preset(self):
        return self.preset or format_presets.HTML5_ZIP

    def process_file(self):
        self.filename = super(HTMLZipFile, self).process_file()
        if self.filename:
            try:
                # make sure index.html exists unless this is a dependency (i.e. shared resources) zip
                if not self.get_preset() == format_presets.HTML5_DEPENDENCY_ZIP:
                    with zipfile.ZipFile(config.get_storage_path(self.filename)) as zf:
                        _info = zf.getinfo('index.html')
            except KeyError as err:
                self.filename = None
                self.error = err
                config.FAILED_FILES.append(self)
        return self.filename


class H5PFile(DownloadFile):
    default_ext = file_formats.H5P
    allowed_formats = [file_formats.H5P]
    is_primary = True

    def get_preset(self):
        return self.preset or format_presets.H5P_ZIP


class VideoFile(DownloadFile):
    default_ext = file_formats.MP4
    allowed_formats = [file_formats.MP4, file_formats.WEBM]
    is_primary = True

    def __init__(self, path, ffmpeg_settings=None, **kwargs):
        self.ffmpeg_settings = ffmpeg_settings
        super(VideoFile, self).__init__(path, **kwargs)

    def get_preset(self):
        return self.preset or guess_video_preset_by_resolution(config.get_storage_path(self.filename))

    def validate(self):
        """
        Ensure `self.path` has one of the extensions in `self.allowed_formats`.
        """
        assert self.path, "{} must have a path".format(self.__class__.__name__)
        ext = extract_path_ext(self.path, default_ext=self.default_ext)
        if ext not in self.allowed_formats and ext not in CONVERTIBLE_FORMATS[format_presets.VIDEO_HIGH_RES]:
            raise ValueError('Incompatible extension {} for VideoFile at {}'.format(ext, self.path))

    def process_unsupported_video_file(self):
        """
        Download video at self.path, convert to mp4, and return converted filename.
        """
        try:
            self.filename = download_and_convert_video(self.path, ffmpeg_settings=self.ffmpeg_settings)
            config.LOGGER.info("\t--- Downloaded and converted {}".format(self.filename))
            return self.filename
        except HTTP_CAUGHT_EXCEPTIONS as err:
            self.error = err
            config.FAILED_FILES.append(self)

    def process_file(self):
        ext = extract_path_ext(self.path, default_ext=self.default_ext)
        if ext not in self.allowed_formats and ext not in CONVERTIBLE_FORMATS[format_presets.VIDEO_HIGH_RES]:
            raise ValueError('Incompatible extension {} for VideoFile at {}'.format(ext, self.path))
        try:
            if ext not in self.allowed_formats:
                # Handle videos that don't have an .mp4 or .webm extension
                self.filename = self.process_unsupported_video_file()
            else:
                # Get copy of video before compression (if specified)
                self.filename = super(VideoFile, self).process_file()
                # Compress the video if compress flag is set or ffmpeg settings were given
                if self.filename and (self.ffmpeg_settings or config.COMPRESS):
                    self.filename = compress_video_file(self.filename, self.ffmpeg_settings)
                    config.LOGGER.info("\t--- Compressed {}".format(self.filename))
        except (BrokenPipeError, CalledProcessError, IOError, VideoCompressionError) as err:
            # Catch errors related to ffmpeg and handle silently
            self.filename = None
            self.error = err
            config.FAILED_FILES.append(self)

        return self.filename


class WebVideoFile(File):
    is_primary = True
    # In future, look into postprocessors and progress_hooks

    def __init__(self, web_url, download_settings=None, high_resolution=False, maxheight=None, **kwargs):
        self.web_url = web_url
        self.download_settings = download_settings or {}
        if "format" not in self.download_settings:
            maxheight = maxheight or (720 if high_resolution else 480)
            # Download the best mp4 format available, or best webm format available, or any other best mp4
            self.download_settings['format'] = "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={maxheight}][ext=webm]+bestaudio[ext=webm]/best[height<={maxheight}][ext=mp4]".format(
                maxheight=maxheight)
            # self.download_settings['recodevideo'] = file_formats.MP4
        super(WebVideoFile, self).__init__(**kwargs)

    def get_preset(self):
        return self.preset or guess_video_preset_by_resolution(config.get_storage_path(self.filename))

    def process_file(self):
        try:
            self.filename = download_from_web(self.web_url, self.download_settings, ext=".{}".format(file_formats.MP4))
            config.LOGGER.info("\t--- Downloaded (YouTube) {}".format(self.filename))

            # Compress if compression flag is set
            if self.filename and config.COMPRESS:
                self.filename = compress_video_file(self.filename, {})
                config.LOGGER.info("\t--- Compressed {}".format(self.filename))

        except youtube_dl.utils.DownloadError as err:
            self.filename = None
            self.error = err
            config.FAILED_FILES.append(self)

        return self.filename

class YouTubeVideoFile(WebVideoFile):
    def __init__(self, youtube_id, **kwargs):
        super(YouTubeVideoFile, self).__init__('http://www.youtube.com/watch?v={}'.format(youtube_id), **kwargs)


def _get_language_with_alpha2_fallback(language_code):
    """
    Lookup language code `language_code` (string) in the internal language codes,
    and if that fails, try to map map `language_code` to the internal represention
    using the `getlang_by_alpha2` helper method.
    Returns either a le-utils Language object or None if both lookups fail.
    """
    # 1. try to lookup `language` using internal representation
    language_obj = languages.getlang(language_code)
    # if language_obj not None, we know `language` is a valid language_id in the internal repr.
    if language_obj is None:
        # 2. try to match by two-letter ISO code
        language_obj = languages.getlang_by_alpha2(language_code)
    return language_obj


def is_youtube_subtitle_file_supported_language(language):
    """
    Check if the language code `language` (string) is a valid language code in the
    internal language id format `{primary_code}` or `{primary_code}-{subcode}`
    ot alternatively if it s YouTube language code that can be mapped to one of
    the languages in the internal represention.
    """
    language_obj = _get_language_with_alpha2_fallback(language)
    if language_obj is None:
        config.LOGGER.warning("Found unsupported language code {}".format(language))
        return False
    else:
        return True


class YouTubeSubtitleFile(File):
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
        self.youtube_url = 'http://www.youtube.com/watch?v={}'.format(youtube_id)
        if isinstance(language, languages.Language):
            language = language.code
        self.youtube_language = language  # save youtube language code (can differ from internal repr.)
        language_obj = _get_language_with_alpha2_fallback(language)
        super(YouTubeSubtitleFile, self).__init__(language=language_obj.code, **kwargs)
        assert self.language, "Subtitles must have a language"

    def get_preset(self):
        return self.preset or format_presets.VIDEO_SUBTITLE

    def process_file(self):
        try:
            self.filename = self.download_subtitle()
            config.LOGGER.info("\t--- Downloaded subtitle {}".format(self.filename))
            return self.filename
        except (FileNotFoundError, youtube_dl.utils.DownloadError):
            self.error = str("Subtitle with langauge {} is not available for {}".format(self.language, self.youtube_url))
            config.FAILED_FILES.append(self)

    def download_subtitle(self):
        settings = {
            'skip_download': True,
            'writesubtitles': True,
            'subtitleslangs': [self.youtube_language],
            'subtitlesformat': "best[ext={}]".format(file_formats.VTT),
            'quiet': True,
            'no_warnings': True
        }
        download_ext = ".{lang}.{ext}".format(lang=self.youtube_language, ext=file_formats.VTT)
        return download_from_web(self.youtube_url, settings, file_format=file_formats.VTT, download_ext=download_ext)


class SubtitleFile(DownloadFile):
    default_ext = file_formats.VTT

    def __init__(self, path, **kwargs):
        """
        If `subtitlesformat` arg is empty, then type will be detected and converted if supported
        """
        self.subtitlesformat = kwargs.get('subtitlesformat', None)
        if "subtitlesformat" in kwargs:
            del kwargs["subtitlesformat"]
        super(SubtitleFile, self).__init__(path, **kwargs)
        assert self.language, "Subtitles must have a language"

    def get_preset(self):
        return self.preset or format_presets.VIDEO_SUBTITLE

    def validate(self):
        """
        Ensure `self.path` has VTT extention OR one of the converible extensions
        in CONVERTIBLE_FORMATS["video_subtitle"] OR otherwise subtiles' format
        info is specified in `self.subtitlesformat`.
        """
        assert self.path, "{} must have a path".format(self.__class__.__name__)
        ext = extract_path_ext(self.path, default_ext=self.subtitlesformat)
        convertible_exts = CONVERTIBLE_FORMATS[self.get_preset()]
        if ext != self.default_ext and ext not in convertible_exts and self.subtitlesformat is None:
            raise ValueError('Incompatible extension {} for SubtitleFile at {}'.format(ext, self.path))

    def process_file(self):
        self.validate()
        caught_errors = HTTP_CAUGHT_EXCEPTIONS + \
            (InvalidSubtitleFormatError, InvalidSubtitleLanguageError)

        try:
            self.filename = self.download_and_transform_file(self.path)
            config.LOGGER.info("\t--- Downloaded {}".format(self.filename))
            return self.filename
        # Catch errors related to reading file path and conversion, and handle silently
        except caught_errors as err:
            self.error = err
            config.FAILED_FILES.append(self)

    def download_and_transform_file(self, path):
        """
        Download subtitles file at `path` and transform it to `.vtt` if necessary.
        Args: path (URL or local path)
        Returns: filename of final .vtt file
        """
        key = "DOWNLOAD:{}".format(path)
        cache_file = get_cache_filename(key)
        if not config.UPDATE and not cache_is_outdated(path, cache_file):
            return cache_file

        config.LOGGER.info("\tDownloading {}".format(path))

        fdin, temp_in_file_name = tempfile.mkstemp()
        fdout, temp_out_file_name = tempfile.mkstemp()

        with open(temp_in_file_name, mode="w+b") as temp_in_file,\
                open(temp_out_file_name, mode="w+b") as temp_out_file:
            write_and_get_hash(path, temp_in_file)
            temp_in_file.seek(0)

            converter = build_subtitle_converter_from_file(temp_in_file.name, self.subtitlesformat)

            # We'll assume the provided file is in the passed language in this case
            if len(converter.get_language_codes()) == 1 \
                    and converter.has_language(LANGUAGE_CODE_UNKNOWN):
                converter.replace_unknown_language(self.language)

            convert_lang_code = self.language

            # Language is not present, let's try different codes
            if not converter.has_language(self.language):
                for lang_code in converter.get_language_codes():
                    language = languages.getlang_by_alpha2(lang_code)

                    if language and language.code == self.language:
                        convert_lang_code = lang_code
                        break
                else:
                    raise InvalidSubtitleLanguageError(
                        "Missing language '{}' in subtitle file".format(self.language))

            converter.write(temp_out_file.name, convert_lang_code)

            temp_out_file.seek(0)
            file_hash = get_hash(temp_out_file.name)

            filename = '{0}.{ext}'.format(file_hash, ext=file_formats.VTT)

            temp_out_file.seek(0)
            copy_file_to_storage(filename, temp_out_file)
            FILECACHE.set(key, bytes(filename, "utf-8"))

        os.close(fdin)
        os.remove(temp_in_file_name)
        os.close(fdout)
        os.remove(temp_out_file_name)
        return filename


class Base64ImageFile(ThumbnailPresetMixin, File):

    def __init__(self, encoding, **kwargs):
        self.encoding = encoding
        super(Base64ImageFile, self).__init__(**kwargs)

    def process_file(self):
        """ process_file: Writes base64 encoding to file
            Args: None
            Returns: filename
        """
        self.filename = self.convert_base64_to_file()
        config.LOGGER.info("\t--- Converted base64 image to {}".format(self.filename))
        return self.filename

    def convert_base64_to_file(self):
        # Get hash of content for cache key
        hashed_content = hashlib.md5()
        hashed_content.update(self.encoding.encode('utf-8'))
        key = "ENCODED: {} (base64 encoded)".format(hashed_content.hexdigest())

        cache_file = get_cache_filename(key)
        if not config.UPDATE and cache_file:
            return cache_file

        config.LOGGER.info("\tConverting base64 to file")

        extension = get_base64_encoding(self.encoding).group(1)
        assert extension in [file_formats.PNG, file_formats.JPG, file_formats.JPEG], "Base64 files must be images in jpg or png format"

        tempf = tempfile.NamedTemporaryFile(suffix=".{}".format(extension), delete=False)
        tempf.close()
        write_base64_to_file(self.encoding, tempf.name)
        filename = "{}.{}".format(get_hash(tempf.name), file_formats.PNG)

        copy_file_to_storage(filename, tempf.name)
        os.unlink(tempf.name)
        FILECACHE.set(key, bytes(filename, "utf-8"))
        return filename


class _ExerciseBase64ImageFile(Base64ImageFile):
    default_ext = file_formats.PNG

    def get_preset(self):
        return self.preset or format_presets.EXERCISE_IMAGE

    def get_replacement_str(self):
        return self.get_filename() or self.encoding


class _ExerciseImageFile(DownloadFile):
    default_ext = file_formats.PNG

    def get_replacement_str(self):
        return self.get_filename() or self.path

    def get_preset(self):
        return self.preset or format_presets.EXERCISE_IMAGE


class _ExerciseGraphieFile(DownloadFile):
    default_ext = file_formats.GRAPHIE

    def __init__(self, path, **kwargs):
        self.original_filename = path.split("/")[-1].split(os.path.sep)[-1].split(".")[0]
        super(_ExerciseGraphieFile, self).__init__(path, **kwargs)

    def get_preset(self):
        return self.preset or format_presets.EXERCISE_GRAPHIE

    def get_replacement_str(self):
        return self.path.split("/")[-1].split(".")[0] or self.path

    def process_file(self):
        """ download: download a web+graphie file
            Args: None
            Returns: None
        """
        try:
            self.filename = self.generate_graphie_file()
            config.LOGGER.info("\t--- Generated graphie {}".format(self.filename))
            return self.filename
        # Catch errors related to reading file path and handle silently
        except (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError) as err:
            self.error = err
            config.FAILED_FILES.append(self)

    def generate_graphie_file(self):
        key = "GRAPHIE: {}".format(self.path)

        cache_file = get_cache_filename(key)
        if not config.UPDATE and cache_file:
            return cache_file

        # Create graphie file combining svg and json files
        with tempfile.TemporaryFile() as tempf:
            # Initialize hash and files
            delimiter = bytes(exercises.GRAPHIE_DELIMITER, 'UTF-8')
            config.LOGGER.info("\tDownloading graphie {}".format(self.original_filename))

            # Write to graphie file
            hash = write_and_get_hash(self.path + ".svg", tempf)
            tempf.write(delimiter)
            hash.update(delimiter)
            hash = write_and_get_hash(self.path + "-data.json", tempf, hash)
            tempf.seek(0)
            filename = "{}.{}".format(hash.hexdigest(), file_formats.GRAPHIE)

            copy_file_to_storage(filename, tempf)

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
        tempf = tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG), delete=False)
        tempf.close()
        try:
            self.extractor_fun(self.path, tempf.name, **self.extractor_kwargs)
            filename = "{}.{}".format(get_hash(tempf.name), file_formats.PNG)
            copy_file_to_storage(filename, tempf.name)
            os.unlink(tempf.name)
            config.LOGGER.info("\t--- Extracted thumbnail {}".format(filename))
            self.filename = filename
        except ThumbnailGenerationError as err:
            config.LOGGER.warning("\t    Failed to extract thumbnail {}".format(err))
            self.filename = None
            self.error = err
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
        raise NotImplementedError('The subclass must implement this method.')


class ExtractedPdfThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {'page_number': 0, 'crop': None}

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_image_from_pdf_page(fpath_in, thumbpath_out, **kwargs)


class ExtractedEPubThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {'crop': None}

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_image_from_epub(fpath_in, thumbpath_out, **kwargs)


class ExtractedHTMLZipThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {'crop': "smart"}

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_image_from_zip(fpath_in, thumbpath_out, **kwargs)


class ExtractedVideoThumbnailFile(ExtractedThumbnailFile):
    extractor_kwargs = {'overwrite': True}

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        extract_thumbnail_from_video(fpath_in, thumbpath_out, **kwargs)


class ExtractedAudioThumbnailFile(ExtractedThumbnailFile):
    studio_cmap_options = {'name': 'BuPu', 'vmin': 0.3, 'vmax': 0.7, 'color': 'black'}
    extractor_kwargs = {'colormap_options': studio_cmap_options}

    def extractor_fun(self, fpath_in, thumbpath_out, **kwargs):
        create_waveform_image(fpath_in, thumbpath_out, **kwargs)


class TiledThumbnailFile(ThumbnailPresetMixin, File):
    allowed_formats = [file_formats.JPG, file_formats.JPEG, file_formats.PNG]

    def __init__(self, source_nodes, **kwargs):
        self.sources = []
        for n in source_nodes:
            images = [f for f in n.files if isinstance(f, ThumbnailFile) and f.get_filename()]
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
        images = [config.get_storage_path(f.get_filename()) for f in self.sources[:num_pictures]]
        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG)) as tempf:
            tempf.close()
            create_tiled_image(images, tempf.name)
            filename = "{}.{}".format(get_hash(tempf.name), file_formats.PNG)
            copy_file_to_storage(filename, tempf.name)
            return filename
