# Node models to represent channel's tree

import os
import hashlib
import tempfile
import shutil
from subprocess import CalledProcessError
from enum import Enum
from le_utils.constants import content_kinds,file_formats, format_presets
from .. import config
from .nodes import ChannelNode, TopicNode, VideoNode, AudioNode, DocumentNode, ExerciseNode, HTML5AppNode
from ..exceptions import UnknownFileTypeError
from pressurecooker.videos import extract_thumbnail_from_video, check_video_resolution, compress_video
from pressurecooker.encodings import get_base64_encoding, write_base64_to_file
from requests.exceptions import MissingSchema, HTTPError, ConnectionError, InvalidURL, InvalidSchema

class FileTypes(Enum):
    """ Enum containing all file types Ricecooker can have

        Steps:
            AUDIO_FILE: mp3 files
            THUMBNAIL: png, jpg, or jpeg files
            DOCUMENT_FILE: pdf files
    """
    AUDIO_FILE = 0
    THUMBNAIL = 1
    DOCUMENT_FILE = 2
    VIDEO_FILE = 3
    YOUTUBE_VIDEO_FILE = 4
    VECTORIZED_VIDEO_FILE = 5
    VIDEO_THUMBNAIL = 6
    YOUTUBE_VIDEO_THUMBNAIL_FILE = 7
    HTML_ZIP_FILE = 8
    SUBTITLE_FILE = 9
    TILED_THUMBNAIL_FILE = 10
    UNIVERSAL_SUBS_SUBTITLE_FILE = 11


FILE_TYPE_MAPPING = {
    content_kinds.AUDIO : {
        file_formats.MP3 : FileTypes.AUDIO_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.DOCUMENT : {
        file_formats.PDF : FileTypes.DOCUMENT_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.HTML5 : {
        file_formats.HTML5 : FileTypes.HTML_ZIP_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.VIDEO : {
        file_formats.MP4 : FileTypes.VIDEO_FILE,
        file_formats.VTT : FileTypes.SUBTITLE_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
}

ALL_FILE_EXTENSIONS = [key for key, value in file_formats.choices]


def guess_file_type(filepath, kind):
    """ guess_file_class: determines what file the content is
        Args:
            filepath (str): filepath of file to check
        Returns: string indicating file's class
    """
    ext = filepath.rsplit('/', 1)[-1].split(".")[-1].lower()
    if kind in FILE_TYPE_MAPPING and ext in FILE_TYPE_MAPPING[kind]:
        return FILE_TYPE_MAPPING[kind][ext]
    return None


class File(object):
    file_size = 0
    preset = None
    filename = None
    original_filename = '[File]'
    node = None
    error = None
    hash = None
    default_ext = None

    def __init__(self, path, preset=None):
        self.path = path
        self.cache_key = path
        self.preset = preset

    def validate(self):
        pass

    def get_preset(self):
        if self.preset:
            return self.preset
        raise NotImplementedError("preset must be set if preset isn't specified when creating File object")

    def to_dict(self):
        return {
            'size' : self.file_size,
            'preset' : self.get_preset(),
            'filename' : self.filename,
            'original_filename' : self.original_filename
        }

    def map_from_downloaded(self, attributes):
        self.file_size = attributes['file_size']
        self.filename = attributes['filename']
        self.original_filename = attributes['original_filename']

    def download(self, track_file=True):
        """ download: downloads file
            Args: None
            Returns: Boolean indicating if file was downloaded
        """
        try:
            # Check cache for file and handle if found
            if config.DOWNLOADER.check_downloaded_file(self):
                config.DOWNLOADER.handle_existing_file(self, track_file=track_file)
                config.LOGGER.info("\tFile {0} already exists (add '-u' flag to update)".format(self.filename))
                return

            config.LOGGER.info("\tDownloading {}".format(self.path))
            self.filename = self.generate_filename()
            self.process_file()

            # Keep track of downloaded file
            config.DOWNLOADER.add_to_downloaded(self, track_file=track_file)

        # Catch errors related to reading file path and handle silently
        except (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError) as err:
            self.error = err
            config.DOWNLOADER.add_to_failed(self)

    def process_file(self, path=None, action="Downloaded"):
        # If file already exists, skip it
        # Otherwise, download file
        if os.path.isfile(config.get_storage_path(self.filename)):
            self.file_size = os.path.getsize(config.get_storage_path(self.filename))
            config.LOGGER.info("\t--- {0} file found at {1}".format(action, self.filename))
        else:
            self.write_file_to_storage(path=path)
            config.LOGGER.info("\t--- {0} file {1}".format(action, self.filename))

    def write_file_to_storage(self, path=None):
        """ write_file_to_storage: reads from file path and writes it to storage
            Args: None
            Returns: None
        """
        path = path if path else self.path
        # Write file to temporary file
        with tempfile.TemporaryFile() as tempf:
            try:
                # Access path
                r = config.SESSION.get(path, stream=True)
                r.raise_for_status()

                # Write to file (generate hash if none provided)
                for chunk in r:
                    tempf.write(chunk)

            except (MissingSchema, InvalidSchema):
                # If path is a local file path, try to open the file (generate hash if none provided)
                with open(path, 'rb') as fobj:
                    tempf.write(fobj.read())

            # Get file metadata (hashed filename, original filename, size)
            self.file_size = tempf.tell()
            tempf.seek(0)

            # Write file to local storage
            with open(config.get_storage_path(self.filename), 'wb') as destf:
                shutil.copyfileobj(tempf, destf)

            if self.file_size == 0:
                raise IOError("File failed to write (corrupted).")

    def generate_filename(self, path=None, force_generate=False):
        """ get_hash: generate hash of file
            Args: None
            Returns: md5 hash of file
        """
        path = path if path else self.path
        if not self.hash or force_generate:
            hash_to_update = hashlib.md5()
            try:
                r = config.SESSION.get(path, stream=True)
                r.raise_for_status()
                for chunk in r:
                    hash_to_update.update(chunk)
            except (MissingSchema, InvalidSchema):
                with open(path, 'rb') as fobj:
                    for chunk in iter(lambda: fobj.read(4096), b""):
                        hash_to_update.update(chunk)
            self.hash = hash_to_update.hexdigest()

        # Get extension of file or default if none found
        extension = os.path.splitext(path)[1][1:].lower()
        if extension not in ALL_FILE_EXTENSIONS:
            if self.default_ext:
                extension = self.default_ext
            else:
                raise IOError("No extension found: {}".format(path))

        return '{0}.{ext}'.format(self.hash, ext=extension)


class ThumbnailFile(File):
    default_ext = file_formats.PNG

    def validate(self):
        assert self.path.endswith(file_formats.JPG) or\
               self.path.endswith(file_formats.JPEG) or\
               self.path.endswith(file_formats.PNG),\
               "Thumbnails must be in jpg, jpeg, or png format"

    def get_preset(self):
        if isinstance(self.node, ChannelNode):
            return format_presets.CHANNEL_THUMBNAIL
        elif isinstance(self.node, VideoNode):
            return format_presets.VIDEO_THUMBNAIL
        elif isinstance(self.node, AudioNode):
            return format_presets.AUDIO_THUMBNAIL
        elif isinstance(self.node, DocumentNode):
            return format_presets.DOCUMENT_THUMBNAIL
        elif isinstance(self.node, ExerciseNode):
            return format_presets.EXERCISE_THUMBNAIL
        elif isinstance(self.node, HTML5AppNode):
            return format_presets.HTML5_THUMBNAIL
        else:
            raise UnknownFileTypeError("Thumbnails are not supported for node kind.")

class ExtractedVideoThumbnailFile(ThumbnailFile):
    def __init__(self, videopath, preset=None):
        self.path = videopath
        self.cache_key = "{} (extracted thumbnail)".format(videopath)
        self.preset = preset

    def get_preset(self):
        return self.preset or format_presets.VIDEO_THUMBNAIL

    def download(self):
        # Check cache for file or derive thumbnail
        if config.DOWNLOADER.check_downloaded_file(self):
            config.DOWNLOADER.handle_existing_file(self)
            config.LOGGER.info("\tImage {0} has already been extracted (add '-u' flag to update)".format(self.filename))
        else:
            self.derive_thumbnail()
            config.DOWNLOADER.add_to_downloaded(self)

    def derive_thumbnail(self):
        """ derive_thumbnail: derive video's thumbnail
            Args: None
            Returns: None
        """
        config.LOGGER.info("\t--- Extracting thumbnail from {}".format(self.path))

        # Otherwise, compress the file
        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG)) as tempf:
            tempf.close()
            extract_thumbnail_from_video(self.path, tempf.name, overwrite=True)
            self.filename = self.generate_filename(path=tempf.name, force_generate=True)
            self.process_file(path=tempf.name, action="Extracted thumbnail")


class AudioFile(File):
    def get_preset(self):
        return self.preset or format_presets.AUDIO

    def validate(self):
        assert self.path.endswith(file_formats.MP3) or\
               self.path.endswith(file_formats.WAV), \
               "Audio files be in mp3 or wav format"


class DocumentFile(File):
    def get_preset(self):
        return self.preset or format_presets.DOCUMENT

    def validate(self):
        assert self.path.endswith(file_formats.PDF), "Document files be in pdf format"


class HTMLZipFile(File):
    def get_preset(self):
        return self.preset or format_presets.HTML5_ZIP

    def validate(self):
        assert self.path.endswith(file_formats.HTML5), "HTML files be in zip format"


class VideoFile(File):
    default_ext = file_formats.MP4

    def __init__(self, path, preset=None, ffmpeg_settings=None):
        self.ffmpeg_settings = ffmpeg_settings
        super(VideoFile, self).__init__(path, preset)

    def get_preset(self):
        return self.preset or check_video_resolution(config.get_storage_path(self.filename))

    def validate(self):
        assert self.path.endswith(file_formats.MP4), "Video files be in mp4 format"

    def download(self):
        # Get copy of video before compression (if specified)
        super(VideoFile, self).download(track_file=self.ffmpeg_settings is None or not config.COMPRESS)
        if self.ffmpeg_settings or config.COMPRESS:
            try:
                # Generate cache key based on settings
                self.cache_key = self.generate_cache_key()

                # Check cache for file or compress file
                if config.DOWNLOADER.check_downloaded_file(self):
                    config.DOWNLOADER.handle_existing_file(self)
                    config.LOGGER.info("\tFile {0} was already compressed (add '-u' flag to update)".format(self.filename))
                else:
                    self.compress_file()
                    config.DOWNLOADER.add_to_downloaded(self)

            # Catch errors related to ffmpeg and handle silently
            except (BrokenPipeError, CalledProcessError, IOError) as err:
                self.error = err
                config.DOWNLOADER.add_to_failed(self)

    def generate_cache_key(self):
        setting_pairs = sorted(["{}:{}".format(k, v) for k, v in self.ffmpeg_settings.items()])
        settings = " ({})".format(":".join(setting_pairs)) if self.ffmpeg_settings else ""
        return "{0}{1}".format(self.path, settings)

    def compress_file(self):
        """ compress_file: compress the video to a lower resolution
            Args: None
            Returns: None
        """
        config.LOGGER.info("\t--- Compressing {}".format(self.path))

        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.MP4)) as tempf:
            tempf.close() # Need to close so pressure cooker can write to file
            compress_video(config.get_storage_path(self.filename), tempf.name, overwrite=True, **self.ffmpeg_settings)
            self.filename = self.generate_filename(path=tempf.name, force_generate=True)
            self.process_file(path=tempf.name, action="Compressed")


# YouTubeVideoFile
# VectorizedVideoFile
# ExtractedVideoThumbnailFile
# YouTubeVideoThumbnailFile
# SubtitleFile
# TiledThumbnailFile
# UniversalSubsSubtitleFile



# class VideoThumbnailFile(ThumbnailFile):

#     def __init__(self, path):
#         self.path = path

#     def get_file(self):
#         if is_url(self.path):
#             storage_path = download(self.path)
#         else:
#             storage_path = copy(self.path)
#         thumbnail_storage_path = extract_thumbnail(storage_path)
#         return thumbnail_storage_path



# class TiledThumbnailFile(ThumbnailFile):

#     def __init__(self, sources):
#         assert len(sources) == 4, "Please provide 4 sources for creating tiled thumbnail"
#         self.sources = [ThumbnailFile(path=source) if isinstance(source, str) else source for source in sources]

#     def get_file(self):
#         images = [source.get_file() for source in self.sources]
#         thumbnail_storage_path = create_tiled_image(images)



# class SubtitleFile(File):

#     def __init__(self, path, language):
#         self.path = path
#         self.language = language

#     def get_file(self):
#         return download_file(self.path)


# class UniversalSubsSubtitleFile(SubtitleFile):

#     def __init__(self, us_id, language):
#         response = sess.get("http://usubs.org/api/{}".format(us_id))
#         path = json.loads(response.content)["subtitle_url"]
#         return super(UniversalSubsSubtitleFile, self).__init__(path=path, language=language)
