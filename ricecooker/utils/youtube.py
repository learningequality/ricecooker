from enum import Enum
import json
import os
import re
import youtube_dl

from pressurecooker.youtube import YouTubeResource
from ricecooker.config import LOGGER


# CONSTANTS for YouTube cache
################################################################################
CHEFDATA_DIR = 'chefdata'
DEFAULT_YOUTUBE_CACHE_DIR = os.path.join(CHEFDATA_DIR, 'youtubecache')


# CONSTANTS for YouTube resources
################################################################################
YOUTUBE_VIDEO_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<youtube_id>[A-Za-z0-9\-=_]{11})'
)
YOUTUBE_PLAYLIST_URL_FORMAT = "https://www.youtube.com/playlist?list={0}"
YOUTUBE_VIDEO_URL_FORMAT = "https://www.youtube.com/watch?v={0}"

class YouTubeTypes(Enum):
    """
    Enum containing YouTube resource types
    """
    YOUTUBE_BASE = "YouTubeBase"
    YOUTUBE_VIDEO = "YouTubeVideo"
    YOUTUBE_PLAYLIST = "YouTubePlayList"
    YOUTUBE_CHANNEL = "YouTubeChannel"

class YouTubeUtils(object):

    def __init__(self, id, type=YouTubeTypes.YOUTUBE_BASE):
        self.id = id
        self.type = type
        self.cache_dir = ''
        self.cache_path = ''
        self.url = ''

    def __str__(self):
        return '%s (%s)' % (self.type, self.cachename)

    def _get_youtube_info(self, use_proxy=True, use_cache=True, options=None):
        youtube_info = None
        # 1. Try to get from cache if allowed:
        if os.path.exists(self.cache_path) and use_cache:
            LOGGER.info("==> [%s] Retrieving cached information...", self.__str__())
            youtube_info = json.load(open(self.cache_path))
        # 2. Fetch info from youtube_dl
        if not youtube_info:
            LOGGER.info("==> [%s] Requesting info from youtube...", self.__str__())
            os.makedirs(self.cache_dir, exist_ok=True)
            try:
                youtube_resource = YouTubeResource(self.url, useproxy=use_proxy)
            except youtube_dl.utils.ExtractorError as e:
                if "unavailable" in str(e):
                    LOGGER.error("==> [%s] Resource unavailable for URL: %s", self.__str__, self.url)
                    return None

            if youtube_resource:
                try:
                    # Save YouTube info to JSON cache file
                    youtube_info = youtube_resource.get_resource_info(options)
                    if youtube_info:
                        json.dump(youtube_info,
                                  open(self.cache_path, 'w'),
                                  indent=4,
                                  ensure_ascii=False,
                                  sort_keys=True)
                    else:
                        LOGGER.error("==> [%s] Failed to extract YouTube info", self.__str__())
                except Exception as e:
                    LOGGER.error("==> [%s] Failed to get YouTube info: %s", self.__str__(), e)
                    return None
        return youtube_info

class YouTubeVideoUtils(YouTubeUtils):

    def __init_subclass__(cls):
        return super().__init_subclass__()

    def __init__(self, id, alias='', cache_dir=''):
        """
        Initializes YouTubeVideoUtils object with id
        :param id: YouTube video ID
        :param alias: Alias name for the JSON cache filename, which will be named as youtube_id if such field not specified
        """
        super().__init__(id, YouTubeTypes.YOUTUBE_VIDEO)
        self.url = YOUTUBE_VIDEO_URL_FORMAT.format(self.id)
        if not alias:
            self.cachename = self.id
        else:
            self.cachename = alias
        if not cache_dir:
            self.cache_dir = DEFAULT_YOUTUBE_CACHE_DIR
        else:
            self.cache_dir = cache_dir
        self.cache_path = os.path.join(self.cache_dir, self.cachename + '.json')

    def get_video_info(self, use_proxy=True, use_cache=True, get_subtitle_languages=False, options=None):
        """
        Get YouTube video info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get video info from local JSON cache, default to True
        :param get_subtitle_languages: Define if need to get info as available subtitle languages, default to False
        :param options: Additional options for youtube_dl.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py
        :return: A ricecooker-like info dict info about the video or None if extraction fails
        """
        extract_options = dict()
        if get_subtitle_languages:
            options_for_subtitles = dict(
                writesubtitles=True,      # extract subtitles info
                allsubtitles=True,        # get all available languages
                writeautomaticsub=False,  # do not include auto-generated subs
            )
            extract_options.update(options_for_subtitles)
        if options:
            extract_options.update(options)
        return self._get_youtube_info(use_proxy=use_proxy, use_cache=use_cache, options=extract_options)

class YouTubePlaylistUtils(YouTubeUtils):

    def __init__(self, id, alias='', cache_dir=''):
        """
        Initializes YouTubePlaylistUtils object with id
        :param id: YouTube playlist ID
        :param alias: Alias name for the JSON cache filename, which will be named as youtube_id if such field not specified
        """
        super().__init__(id, YouTubeTypes.YOUTUBE_PLAYLIST)
        self.url = YOUTUBE_PLAYLIST_URL_FORMAT.format(self.id)
        if not alias:
            self.cachename = self.id
        else:
            self.cachename = alias
        if not cache_dir:
            self.cache_dir = DEFAULT_YOUTUBE_CACHE_DIR
        else:
            self.cache_dir = cache_dir
        self.cache_path = os.path.join(self.cache_dir, self.cachename + '.json')

    def get_playlist_info(self, use_proxy=True, use_cache=True, youtube_skip_download=True, options=None):
        """
        Get YouTube playlist info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get playlist info from local JSON cache, default to True
        :param youtube_skip_download: Skip the actual download of the YouTube video files
        :param options: Additional options for youtube_dl.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py
        :return: A ricecooker-like info dict info about the playlist or None if extraction fails
        """
        youtube_extract_options = dict(
            skip_download=youtube_skip_download,
            extract_flat=True
        )
        if options:
            youtube_extract_options.update(options)
        return self._get_youtube_info(use_proxy=use_proxy, use_cache=use_cache, options=youtube_extract_options)
