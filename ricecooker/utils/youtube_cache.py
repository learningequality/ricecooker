import json
import os
import re
import youtube_dl

from pressurecooker.youtube import YouTubeResource
from ricecooker.config import LOGGER


# CONSTANTS for YouTube cache
################################################################################
CHEFDATA_DIR = 'chefdata'
YOUTUBE_CACHE_DIR = os.path.join(CHEFDATA_DIR, 'youtubecache')
if not os.path.exists(YOUTUBE_CACHE_DIR):
    os.makedirs(YOUTUBE_CACHE_DIR)


# CONSTANTS for YouTube resources
################################################################################
YOUTUBE_VIDEO_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<youtube_id>[A-Za-z0-9\-=_]{11})'
)
YOUTUBE_PLAYLIST_URL_FORMAT = "https://www.youtube.com/playlist?list={0}"
YOUTUBE_VIDEO_URL_FORMAT = "https://www.youtube.com/watch?v={0}"


class YouTubeVideoCache(object):

    def __init__(self, video_id, alias=''):
        """
        Initializes YouTubeVideoCache object with video_id
        :param alias: Alias name for the JSON cache filename, which will be named as youtube_id if such field not specified
        """
        self.video_id = video_id
        self.url = YOUTUBE_VIDEO_URL_FORMAT.format(self.video_id)
        if not alias:
            self.cachename = alias
        else:
            self.cachename = self.video_id
        if not os.path.isdir(YOUTUBE_CACHE_DIR):
            os.mkdir(YOUTUBE_CACHE_DIR)
        self.vinfo_json_path = os.path.join(YOUTUBE_CACHE_DIR, self.cachename + '.json')

    def __str__(self):
        return 'YouTubeVideoCache (%s)' % (self.cachename)

    def get_video_info(self, use_cache=True, options=None):
        """
        Get YouTube video info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get video info from local JSON cache, default to True
        :param options: Additional options for youtube_dl.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py
        :return: A ricecooker-like info dict info about the video or None if extraction fails
        """
        # 1. Try to get from cache if allowed:
        vinfo = None
        if use_cache and os.path.exists(self.vinfo_json_path):
            vinfo = json.load(open(self.vinfo_json_path))
            LOGGER.info("==> [Video %s] Retrieving cached video information...", self.cachename)
        # 2. Fetch info from youtube_dl
        if not vinfo:
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
                    vinfo = video.get_resource_info(options)
                    json.dump(vinfo,
                              open(self.vinfo_json_path, 'w'),
                              indent=4,
                              ensure_ascii=False,
                              sort_keys=True)
                except Exception as e:
                    LOGGER.error("==> [Video %s] Failed to get video info: %s", self.cachename, e)
                    return None
            else:
                return None
        return vinfo


class YouTubePlaylistCache(object):

    def __init__(self, playlist_id, alias=''):
        """
        Initializes YouTubePlaylistCache object
        :param alias: Alias name for the JSON cache filename, which will be named as playlist_id if such field not specified
        """
        self.playlist_id = playlist_id
        if not alias:
            self.cachename = alias
        else:
            self.cachename = self.playlist_id
        if not os.path.isdir(YOUTUBE_CACHE_DIR):
            os.mkdir(YOUTUBE_CACHE_DIR)
        self.playlist_info_json_path = os.path.join(YOUTUBE_CACHE_DIR, self.cachename + '.json')

    def __str__(self):
        return 'YouTubePlaylistCache (%s)' % (self.cachename)

    def get_playlist_info(self, use_cache=True, youtube_ignore_error=True, youtube_skip_download=True, options=None):
        """
        Get YouTube playlist info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get playlist info from local JSON cache, default to True
        :param youtube_ignore_error: Do not stop on download errors.
                                     Please enable this option when videos of playlist is private or deleted thus extraction won't be blocked on those videos
        :param youtube_skip_download: Skip the actual download of the YouTube video files
        :param options: Additional options for youtube_dl.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py
        :return: A ricecooker-like info dict info about the playlist or None if extraction fails
        """
        playlist_info = None
        if os.path.exists(self.playlist_info_json_path) and use_cache:
            LOGGER.info("==> [Playlist %s] Retrieving cached playlist information...", self.cachename)
            playlist_info = json.load(open(self.playlist_info_json_path))

        if not playlist_info:
            playlist_url = YOUTUBE_PLAYLIST_URL_FORMAT.format(self.playlist_id)
            playlist_resource = YouTubeResource(playlist_url)
            youtube_extract_options = dict(
                ignoreerrors=youtube_ignore_error,
                skip_download=youtube_skip_download
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
                              open(self.playlist_info_json_path, 'w'),
                              indent=4,
                              ensure_ascii=False,
                              sort_keys=False)
                    LOGGER.info("==> [Playlist %s] Successfully get playlist info", self.cachename)
                except Exception as e:
                    LOGGER.error("==> [Playlist %s] Failed to get playlist info: %s", self.cachename, e)
                    return None
        return playlist_info
