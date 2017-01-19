# Node models to represent channel's tree

import os
import hashlib
import tempfile
import shutil
from subprocess import CalledProcessError
from enum import Enum
from le_utils.constants import content_kinds,file_formats, format_presets, exercises
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
    BASE64_FILE = 12


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
    content_kinds.EXERCISE : {
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
}

# from cachecontrol.caches.file_cache import FileCache

# CACHE = FileCache(".filecache")

def guess_file_type(filepath, kind):
    """ guess_file_class: determines what file the content is
        Args:
            filepath (str): filepath of file to check
        Returns: string indicating file's class
    """
    if get_base64_encoding(filepath):
        return FileTypes.BASE64_FILE
    ext = filepath.rsplit('/', 1)[-1].split(".")[-1].lower()
    if kind in FILE_TYPE_MAPPING and ext in FILE_TYPE_MAPPING[kind]:
        return FILE_TYPE_MAPPING[kind][ext]
    return None

def download(path, default_ext=None):
    """ download: downloads file
        Args: None
        Returns: filename
    """
    key = "DOWNLOAD:{}".format(path)
    if config.DOWNLOADER.get(key):
        return config.DOWNLOADER.get(key)

    config.LOGGER.info("\tDownloading {}".format(path))

    # Write file to temporary file
    with tempfile.TemporaryFile() as tempf:
        hash = write_and_get_hash(path, tempf)
        tempf.seek(0)

        # Get extension of file or default if none found
        extension = os.path.splitext(path)[1][1:].lower()
        if extension not in [key for key, value in file_formats.choices]:
            if default_ext:
                extension = default_ext
            else:
                raise IOError("No extension found: {}".format(path))

        filename = '{0}.{ext}'.format(hash.hexdigest(), ext=extension)

        # Write file to local storage
        with open(config.get_storage_path(filename), 'wb') as destf:
            shutil.copyfileobj(tempf, destf)

        config.DOWNLOADER.set(key, filename)

        return filename

def write_and_get_hash(path, write_to_file, hash=None):
    """ write_and_get_hash: write file
        Args: None
        Returns: Hash of file's contents
    """
    hash = hash or hashlib.md5()
    try:
        # Access path
        r = config.SESSION.get(path, stream=True)
        r.raise_for_status()
        for chunk in r:
            write_to_file.write(chunk)
            hash.update(chunk)

    except (MissingSchema, InvalidSchema):
        # If path is a local file path, try to open the file (generate hash if none provided)
        with open(path, 'rb') as fobj:
            for chunk in iter(lambda: fobj.read(4096), b""):
                write_to_file.write(chunk)
                hash.update(chunk)

    assert write_to_file.tell() > 0, "File failed to write (corrupted)."

    return hash

def get_hash(filepath):
    hash = hashlib.md5()
    with open(filepath, 'rb') as fobj:
        for chunk in iter(lambda: fobj.read(4096), b""):
            hash.update(chunk)
    return hash.hexdigest()

def compress(filename, ffmpeg_settings):
    # Generate key for compressed file
    setting_list = ffmpeg_settings if ffmpeg_settings else {}
    setting_pairs = sorted(["{}:{}".format(k, v) for k, v in setting_list.items()])
    settings = " ({})".format(":".join(setting_pairs)) if ffmpeg_settings else " (default compression)"
    key = "{0}{1}".format(filename, settings)

    if config.DOWNLOADER.get(key):
        return config.DOWNLOADER.get(key)

    config.LOGGER.info("\t--- Compressing {}".format(filename))

    with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.MP4)) as tempf:
        tempf.close() # Need to close so pressure cooker can write to file
        compress_video(config.get_storage_path(filename), tempf.name, overwrite=True, **setting_list)
        filename = "{}.{}".format(get_hash(tempf.name), file_formats.MP4)

        # Write file to local storage
        with open(tempf.name, 'rb') as srcf, open(config.get_storage_path(filename), 'wb') as destf:
            shutil.copyfileobj(srcf, destf)

        config.DOWNLOADER.set(key, filename)
        return filename



class File(object):
    original_filename = '[File]'
    node = None
    error = None
    default_ext = None
    filename = None
    assessment_item = None

    def __init__(self, preset=None, language=None):
        self.preset = preset
        self.language = language

    def validate(self):
        pass

    def get_preset(self):
        if self.preset:
            return self.preset
        raise NotImplementedError("preset must be set if preset isn't specified when creating File object")

    def get_filename(self):
        if self.filename:
            return self.filename
        return self.process_file()

    def to_dict(self):
        filename = self.get_filename()

        # If file was successfully downloaded, return dict
        # Otherwise return None
        if filename:
            return {
                'size' : os.path.getsize(config.get_storage_path(filename)),
                'preset' : self.get_preset(),
                'filename' : filename,
                'original_filename' : self.original_filename,
                'language' : self.language,
            }
        return None

    def process_file(self):
        # Overwrite in subclasses
        pass

class DownloadFile(File):
    def __init__(self, path, **kwargs):
        self.path = path
        super(DownloadFile, self).__init__(**kwargs)

    def validate(self):
        assert self.path, "Download files must have a path"

    def process_file(self):
        try:
            self.filename = download(self.path, default_ext=self.default_ext)
            config.LOGGER.info("\t--- Downloaded {}".format(self.filename))
            return self.filename
        # Catch errors related to reading file path and handle silently
        except (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError, AssertionError) as err:
            self.error = err
            config.FAILED_FILES.append(self)

class ThumbnailFile(DownloadFile):
    default_ext = file_formats.PNG
    language = None

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

class AudioFile(DownloadFile):
    def get_preset(self):
        return self.preset or format_presets.AUDIO

    def validate(self):
        assert self.path.endswith(file_formats.MP3) or\
               self.path.endswith(file_formats.WAV), \
               "Audio files must be in mp3 or wav format"

class DocumentFile(DownloadFile):
    def get_preset(self):
        return self.preset or format_presets.DOCUMENT

    def validate(self):
        assert self.path.endswith(file_formats.PDF), "Document files must be in pdf format"

class HTMLZipFile(DownloadFile):
    def get_preset(self):
        return self.preset or format_presets.HTML5_ZIP

    def validate(self):
        assert self.path.endswith(file_formats.HTML5), "HTML files must be in zip format"

class ExtractedVideoThumbnailFile(DownloadFile):

    def get_preset(self):
        return self.preset or format_presets.VIDEO_THUMBNAIL

    def process_file(self):
        self.filename = self.derive_thumbnail()
        config.LOGGER.info("\t--- Extracted thumbnail {}".format(self.filename))
        return self.filename

    def derive_thumbnail(self):
        key = "{} (extracted thumbnail)".format(self.path)
        if config.DOWNLOADER.get(key):
            return config.DOWNLOADER.get(key)

        config.LOGGER.info("\t--- Extracting thumbnail from {}".format(self.path))
        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG)) as tempf:
            tempf.close()
            extract_thumbnail_from_video(self.path, tempf.name, overwrite=True)
            filename = "{}.{}".format(get_hash(tempf.name), file_formats.PNG)

            # Write file to local storage
            with open(tempf.name, 'rb') as srcf, open(config.get_storage_path(filename), 'wb') as destf:
                shutil.copyfileobj(srcf, destf)

            config.DOWNLOADER.set(key, filename)
            return filename


class VideoFile(DownloadFile):
    default_ext = file_formats.MP4

    def __init__(self, path, ffmpeg_settings=None, **kwargs):
        self.ffmpeg_settings = ffmpeg_settings
        super(VideoFile, self).__init__(path, **kwargs)

    def get_preset(self):
        return self.preset or check_video_resolution(config.get_storage_path(self.filename))

    def validate(self):
        assert self.path.endswith(file_formats.MP4), "Video files be in mp4 format"

    def process_file(self):
        try:
            # Get copy of video before compression (if specified)
            self.filename = super(VideoFile, self).process_file()
            if self.filename and (self.ffmpeg_settings or config.COMPRESS):
                self.filename = compress(self.filename, self.ffmpeg_settings)
                config.LOGGER.info("\t--- Compressed {}".format(self.filename))
            return self.filename
        # Catch errors related to ffmpeg and handle silently
        except (BrokenPipeError, CalledProcessError, IOError) as err:
            error = err
            config.FAILED_FILES.append(self)


class SubtitleFile(DownloadFile):
    def __init__(self, path, language, **kwargs):
        assert language, "Subtitles must have a language"
        super(SubtitleFile, self).__init__(path, language=language, **kwargs)

    def get_preset(self):
        return self.preset or format_presets.VIDEO_SUBTITLE

    def validate(self):
        assert self.path.endswith(file_formats.VTT), "Subtitle files must be in vtt format"


class ExerciseImageFile(DownloadFile):
    default_ext = file_formats.PNG

    def get_replacement_str(self):
        return self.get_filename() or self.path

    def get_preset(self):
        return self.preset or format_presets.EXERCISE_IMAGE

class Base64ImageFile(File):

    def __init__(self, encoding, **kwargs):
        self.encoding = encoding
        super(Base64ImageFile, self).__init__(**kwargs)

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
        key = hashed_content.hexdigest() + " (base64 encoded)"

        if config.DOWNLOADER.get(key):
            return config.DOWNLOADER.get(key)

        config.LOGGER.info("\tConverting base64 to file")

        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG)) as tempf:
            tempf.close()
            write_base64_to_file(self.encoding, tempf.name)
            filename = "{}.{}".format(get_hash(tempf.name), file_formats.PNG)

            # Write file to local storage
            with open(tempf.name, 'rb') as srcf, open(config.get_storage_path(filename), 'wb') as destf:
                shutil.copyfileobj(srcf, destf)
            config.DOWNLOADER.set(key, filename)
            return filename


class ExerciseBase64ImageFile(Base64ImageFile):
    default_ext = file_formats.PNG

    def get_preset(self):
        return self.preset or format_presets.EXERCISE_IMAGE

    def get_replacement_str(self):
        return self.get_filename() or self.encoding

class ExerciseGraphieFile(DownloadFile):
    default_ext = file_formats.GRAPHIE

    def __init__(self, path, **kwargs):
        self.original_filename = path.split("/")[-1].split(".")[0]
        super(ExerciseGraphieFile, self).__init__(path, **kwargs)

    def get_preset(self):
        return self.preset or format_presets.EXERCISE_GRAPHIE

    def get_replacement_str(self):
        return self.original_filename or self.path

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
        key = "GRAPHIE:{}".format(self.path)

        if config.DOWNLOADER.get(key):
            return config.DOWNLOADER.get(key)

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

            # Write file to local storage
            with open(config.get_storage_path(filename), 'wb') as destf:
                shutil.copyfileobj(tempf, destf)

            config.DOWNLOADER.set(key, filename)
            return filename



class YouTubeVideoFile(File):
    def __init__(self, youtube_id, youtube_dl_settings=None, **kwargs):
        self.youtube_id = youtube_id
        self.youtube_dl_settings = youtube_dl_settings or {}
        self.youtube_dl_settings['format'] = file_formats.MP4
        super(YouTubeVideoFile, self).__init__(**kwargs)
        # postprocessors, progress_hooks,

    def get_preset(self):
        return self.preset or check_video_resolution(config.get_storage_path(self.filename))

    def process_file(self):
        pass

class YouTubeHighResolutionVideoFile(YouTubeVideoFile):
    def __init__(self, youtube_id, youtube_dl_settings=None, **kwargs):
        self.youtube_id = youtube_id
        self.youtube_dl_settings = youtube_dl_settings or {}
        self.youtube_dl_settings['format'] = "bestvideo[ext={}]" # file_formats.MP4
        super(YouTubeHighResolutionVideoFile, self).__init__(**kwargs)
        # postprocessors, progress_hooks, EMBEDDING

    def get_preset(self):
        return self.preset or check_video_resolution(config.get_storage_path(self.filename))

    def process_file(self):
        pass


class YouTubeHighResolutionVideoFile(YouTubeVideoFile):
    def __init__(self, youtube_id, youtube_dl_settings=None, **kwargs):
        self.youtube_id = youtube_id
        self.youtube_dl_settings = youtube_dl_settings or {}
        self.youtube_dl_settings['format'] = "worstvideo" # file_formats.MP4
        super(YouTubeHighResolutionVideoFile, self).__init__(**kwargs)
        # postprocessors, progress_hooks,

    def get_preset(self):
        return self.preset or check_video_resolution(config.get_storage_path(self.filename))

    def process_file(self):
        pass

# YouTubeVideoThumbnailFile


# VectorizedVideoFile

# TiledThumbnailFile
# UniversalSubsSubtitleFile


# class TiledThumbnailFile(ThumbnailFile):
#     def __init__(self, sources):
#         assert len(sources) == 4, "Please provide 4 sources for creating tiled thumbnail"
#         self.sources = [ThumbnailFile(path=source) if isinstance(source, str) else source for source in sources]

#     def get_file(self):
#         images = [source.get_file() for source in self.sources]
#         thumbnail_storage_path = create_tiled_image(images)


# class UniversalSubsSubtitleFile(SubtitleFile):
#     def __init__(self, us_id, language):
#         response = sess.get("http://usubs.org/api/{}".format(us_id))
#         path = json.loads(response.content)["subtitle_url"]
#         return super(UniversalSubsSubtitleFile, self).__init__(path=path, language=language)
