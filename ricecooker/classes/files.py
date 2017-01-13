# Node models to represent channel's tree

import os
import hashlib
import tempfile
from enum import Enum
from le_utils.constants import content_kinds,file_formats, format_presets
from .. import config
from pressurecooker.videos import extract_thumbnail_from_video, check_video_resolution, compress_video
from pressurecooker.encodings import get_base64_encoding, write_base64_to_file
from requests.exceptions import MissingSchema, HTTPError, ConnectionError, InvalidURL, InvalidSchema

class FileTypes(Enum):
    """ Enum containing all file types Ricecooker can have

        Steps:
            AUDIOFILE: mp3 files
            THUMBNAIL: png, jpg, or jpeg files
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

    def __init__(self, path, preset=None):
        self.path = path
        self.cache_key = path
        self.preset = preset

    def get_preset(self, node=None):
        if self.preset:
            return preset
        raise NotImplementedError("get_preset must be overridden if preset isn't specified when creating File object")

    def to_dict(self):
        return {
            'size' : self.file_size,
            'preset' : self.preset,
            'filename' : self.filename,
            'original_filename' : self.original_filename
        }

    def map_from_downloaded(self, attributes):
        self.file_size = attributes['file_size']
        self.preset = attributes['preset']
        self.filename = attributes['filename']
        self.original_filename = attributes['original_filename']

    def download(self):
        """ download: downloads file
            Args: None
            Returns: None
        """
        try:
            # Check cache for file and handle if found
            if config.DOWNLOADER.check_downloaded_file(self):
                config.DOWNLOADER.handle_existing_file(self)
                return

            config.LOGGER.info("\tDownloading {}".format(self.path))
            hash = self.get_hash()

            # Get extension of file or default if none found
            extension = os.path.splitext(self.path)[1][1:].lower()
            if extension not in ALL_FILE_EXTENSIONS:
                if default_ext:
                    extension = default_ext
                else:
                    raise IOError("No extension found: {}".format(self.path))

            self.filename = '{0}.{ext}'.format(hash.hexdigest(), ext=extension)

            # If file already exists, skip it
            if os.path.isfile(config.get_storage_path(self.filename)):
                config.LOGGER.info("\t--- No changes detected on {0}".format(self.filename))

                # Keep track of downloaded file
                self.file_size = os.path.getsize(config.get_storage_path(self.filename))
                config.DOWNLOADER.add_to_downloaded(self)

            # Otherwise, download file
            else:
                # Write file to temporary file
                with tempfile.TemporaryFile() as tempf:
                    try:
                        # Access path
                        r = config.SESSION.get(self.path, stream=True)
                        r.raise_for_status()

                        # Write to file (generate hash if none provided)
                        for chunk in r:
                            tempf.write(chunk)

                    except (MissingSchema, InvalidSchema):
                        # If path is a local file path, try to open the file (generate hash if none provided)
                        with open(self.path, 'rb') as fobj:
                            tempf.write(fobj.read())

                    # Get file metadata (hashed filename, original filename, size)
                    self.file_size = tempf.tell()
                    tempf.seek(0)

                    # Write file to local storage
                    with open(config.get_storage_path(self.filename), 'wb') as destf:
                        shutil.copyfileobj(tempf, destf)

                    # Keep track of downloaded file
                    config.add_to_downloaded(self)
                    config.LOGGER.info("\t--- Downloaded {}".format(self.filename))

        # Catch errors related to reading file path and handle silently
        except (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError) as err:
            self.error = err
            config.DOWNLOADER.add_to_failed(self)

    def get_hash(self):
        """ get_hash: generate hash of file
            Args: None
            Returns: md5 hash of file
        """
        hash_to_update = hashlib.md5()
        try:
            r = config.SESSION.get(self.path, stream=True)
            r.raise_for_status()
            for chunk in r:
                hash_to_update.update(chunk)
        except (MissingSchema, InvalidSchema):
            with open(self.path, 'rb') as fobj:
                for chunk in iter(lambda: fobj.read(4096), b""):
                    hash_to_update.update(chunk)
        return hash_to_update

class ThumbnailFile(File):
    def __init__(self, path):
        super(ThumbnailFile, self).__init__(path)

class AudioFile(File):
    def __init__(self, path):
        super(AudioFile, self).__init__(path)

class DocumentFile(File):
    def __init__(self, path):
        super(DocumentFile, self).__init__(path)

# VideoFile
# YouTubeVideoFile
# VectorizedVideoFile
# VideoThumbnailFile
# YouTubeVideoThumbnailFile
# ThumbnailFile
# AudioFile
# DocumentFile
# HTMLZIP
# SubtitleFile
# TiledThumbnailFile
# UniversalSubsSubtitleFile

# class VideoFile(File):

#     def __init__(self, path, ffmpeg_settings=None):
#         self.path = path
#         self.ffmpeg_settings = ffmpeg_settings

#     def get_preset(self, node=Node):
#         if ...
#             return presets.VIDEO_HIGH_RES
#         else:
#             return presets.VIDEO_LOW_RES

#     def get_file(self):

#         videopath = download_file(self.path)

#         if self.ffmpeg_settings:
#             cache_key = "ffmpegconvert:{sourcepath}:{max_width}:{clf}".format({
#                 "sourcepath": videopath,
#                 "max_width": self.ffmpeg_settings["max_width"],
#                 "clf": self.ffmpeg_settings["clf"],
#             })
#             if cache.has_key(cache_key):
#                 videopath = cache.get(cache_key)
#             else:
#                 videopath = ffmpeg_compress_video(source, settings=ffmpeg_settings)
#                 cache.set(cache_key, videopath)

#         return videopath


# class ThumbnailFile(File):

#     def get_preset(self, node=None):
#         if isinstance(node, Video):
#             return presets.VIDEO_THUMBNAIL
#         elif ...


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


# videofile = VideoFile(path=video_url, max_width=600, clf=35)
# return VideoNode(files=[videofile], title="Blah", id="woooo")




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
