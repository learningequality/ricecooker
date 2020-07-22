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


class YouTubeUtils(object):

    def __init__(self, id, alias='', cache_dir=''):
        """
        Initializes YouTubeUtils object with id
        :param id: YouTube resource ID, could be either YouTube video ID or playlist ID
        :param alias: Alias name for the JSON cache filename, which will be named as youtube_id if such field not specified
        """
        self.id = id
        if not alias:
            self.cachename = self.id
        else:
            self.cachename = alias
        if not cache_dir:
            self.cache_dir = DEFAULT_YOUTUBE_CACHE_DIR
        else:
            self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.json_path = os.path.join(self.cache_dir, self.cachename + '.json')

    def __str__(self):
        return 'YouTubeUtils (%s)' % (self.cachename)

    def get_video_info(self, use_cache=True, get_subtitle_languages=False, options=None):
        """
        Get YouTube video info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get video info from local JSON cache, default to True
        :param get_subtitle_languages: Define if need to get info as available subtitle languages, default to False
        :param options: Additional options for youtube_dl.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py
        :return: A ricecooker-like info dict info about the video or None if extraction fails
        """
        # 1. Try to get from cache if allowed:
        vinfo = None
        if use_cache and os.path.exists(self.json_path):
            vinfo = json.load(open(self.json_path))
            LOGGER.info("==> [Video %s] Retrieving cached video information...", self.cachename)
        # 2. Fetch info from youtube_dl
        if not vinfo:
            self.url = YOUTUBE_VIDEO_URL_FORMAT.format(self.id)
            LOGGER.info("==> [Video %s] Requesting %s from youtube...", self.cachename, self.url)
            try:
                video = YouTubeResource(self.url)
            except youtube_dl.utils.ExtractorError as e:
                if "unavailable" in str(e):
                    LOGGER.error("==> [Video %s] Video not found at URL: %s", self.cachename, self.url)
                    return None

            if video:
                try:
                    # Save video info to JSON cache file
                    extract_options = dict()
                    if get_subtitle_languages:
                        options_for_subtitles = dict(
                            writesubtitles = True,      # extract subtitles info
                            allsubtitles = True,        # get all available languages
                            writeautomaticsub = False,  # do not include auto-generated subs
                        )
                        extract_options.update(options_for_subtitles)
                    if options:
                        extract_options.update(options)
                    vinfo = video.get_resource_info(extract_options)
                    json.dump(vinfo,
                              open(self.json_path, 'w'),
                              indent=4,
                              ensure_ascii=False,
                              sort_keys=True)
                except Exception as e:
                    LOGGER.error("==> [Video %s] Failed to get video info: %s", self.cachename, e)
                    return None
            else:
                return None
        return vinfo

    def get_playlist_info(self, use_cache=True, youtube_skip_download=True, options=None):
        """
        Get YouTube playlist info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get playlist info from local JSON cache, default to True
        :param youtube_skip_download: Skip the actual download of the YouTube video files
        :param options: Additional options for youtube_dl.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py
        :return: A ricecooker-like info dict info about the playlist or None if extraction fails
        """
        playlist_info = None
        if os.path.exists(self.json_path) and use_cache:
            LOGGER.info("==> [Playlist %s] Retrieving cached playlist information...", self.cachename)
            playlist_info = json.load(open(self.json_path))

        if not playlist_info:
            playlist_url = YOUTUBE_PLAYLIST_URL_FORMAT.format(self.id)
            playlist_resource = YouTubeResource(playlist_url)
            youtube_extract_options = dict(
                skip_download=youtube_skip_download,
                extract_flat=True
            )
            if options:
                youtube_extract_options.update(options)
            if playlist_resource:
                try:
                    playlist_info = playlist_resource.get_resource_info(youtube_extract_options)
                    # Traverse through the video list to remove duplicates
                    video_set = set()
                    videos = playlist_info.get('children')
                    for video in videos:
                        if video['id'] in video_set:
                            videos.remove(video)
                        else:
                            video_set.add(video['id'])

                    json.dump(playlist_info,
                              open(self.json_path, 'w'),
                              indent=4,
                              ensure_ascii=False,
                              sort_keys=False)
                    LOGGER.info("==> [Playlist %s] Successfully get playlist info", self.cachename)
                except Exception as e:
                    LOGGER.error("==> [Playlist %s] Failed to get playlist info: %s", self.cachename, e)
                    return None
        return playlist_info
