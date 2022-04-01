import copy
import json
import logging
import os
import re
import time
from datetime import datetime
from enum import Enum

import yt_dlp
from le_utils.constants import languages

from . import proxy
from . import utils


LOGGER = logging.getLogger("YouTubeResource")
LOGGER.setLevel(logging.DEBUG)


NON_NETWORK_ERRORS = [
    yt_dlp.utils.ExtractorError,  # private and unlisted videos
    yt_dlp.utils.PostProcessingError,  # custom postprocessors failures
]


def get_youtube_info(youtube_url):
    """
    Convenience function for retrieving YouTube resource information. Wraps YouTubeResource.get_resource_info.

    :param youtube_url: URL of YouTube resource to get information on.

    :return: A dictionary object containing information about the YouTube resource.
    """
    resource = YouTubeResource(youtube_url)
    return resource.get_resource_info()


class YouTubeResource(object):
    """
    This class encapsulates functionality for information retrieval and download
    of YouTube resources. Resources may include videos, playlists and channels.
    """

    # If extract_info request takes longer than this we treat it as broken proxy
    EXTRACT_TIME_SLOW_LIMIT = 20  # in seconds

    def __init__(self, url, useproxy=True, high_resolution=False, options=None):
        """
        Initializes the YouTube resource, and calls the get_resource_info method to retrieve resource information.

        :param url: URL of a YouTube resource. URL may point to a video, playlist or channel.
        """
        if "youtube.com" not in url and "youtu.be" not in url:
            raise utils.VideoURLFormatError(url, "YouTube")
        self.url = url
        self.subtitles = {}
        self.num_retries = 10
        self.sleep_seconds = 0.5
        self.preferred_formats = {"video": "mp4", "audio": "m4a"}
        self.useproxy = useproxy
        self.high_resolution = high_resolution
        self.options = options
        self.client = None  # this will become a YoutubeDL instance on first use
        self.info = None  # save detailed info_dict returned from extract_info

    def get_resource_info(self, options=None):  # noqa: C901
        """
        This method checks the YouTube URL, then returns a dictionary object with info about the video(s) in it.

        :return: A ricecooker-like dict of info about the channel, playlist or video.
        """
        extract_info_options = dict(
            verbose=True,  # TODO(ivan) change this to quiet = True eventually
            no_warnings=True,
            no_color=True,
            # By default, YouTubeDL will pick what it determines to be the best formats, but for consistency's sake
            # we want to always get preferred formats (default of mp4 and m4a) when possible.
            format="bestvideo[height<={maxheight}][ext={vext}]+bestaudio[ext={aext}]/best[height<={maxheight}][ext={vext}]".format(
                maxheight=720 if self.high_resolution else 480,
                vext=self.preferred_formats["video"],
                aext=self.preferred_formats["audio"],
            ),
        )

        for i in range(self.num_retries):
            if self.useproxy:
                dl_proxy = proxy.choose_proxy()
                extract_info_options["proxy"] = dl_proxy
            if self.options:
                extract_info_options.update(self.options)  # init-time options
            if options:
                extract_info_options.update(options)  # additional options

            try:
                LOGGER.debug("YoutubeDL options = {}".format(extract_info_options))
                self.client = yt_dlp.YoutubeDL(extract_info_options)
                self.client.add_default_info_extractors()

                LOGGER.debug("Calling extract_info for URL {}".format(self.url))
                start_time = datetime.now()
                self.info = self.client.extract_info(
                    self.url, download=False, process=True
                )
                end_time = datetime.now()

                # Mark slow proxies as broken
                extract_time = (end_time - start_time).total_seconds()
                LOGGER.debug("extract_time = " + str(extract_time))
                if self.useproxy and extract_time > self.EXTRACT_TIME_SLOW_LIMIT:
                    if "entries" in self.info:
                        pass  # it's OK for extract_info to be slow for playlists
                    else:
                        proxy.record_error_for_proxy(
                            dl_proxy,
                            exception="extract_info took " + extract_time + " seconds",
                        )
                        LOGGER.info("Found slow proxy {}".format(dl_proxy))

                # Format info JSON into ricecooker-like keys
                edited_results = self._format_for_ricecooker(self.info)
                return edited_results

            except Exception as e:
                network_related_error = True
                if isinstance(e, yt_dlp.utils.DownloadError):
                    (eclass, evalue, etraceback) = e.exc_info
                    if eclass in NON_NETWORK_ERRORS:
                        network_related_error = False
                if self.useproxy and network_related_error:
                    # Add the current proxy to the BROKEN_PROXIES list
                    proxy.record_error_for_proxy(dl_proxy, exception=e)
                LOGGER.warning(e)
                if i < self.num_retries - 1:
                    LOGGER.warning("Info extraction failed, retrying...")
                    time.sleep(self.sleep_seconds)

    def get_dir_name_from_url(self, url=None):
        """
        Takes a URL and returns a directory name to store files in.

        :param url: URL of a YouTube resource, if None, defaults to the url passed to the YouTubeResource object
        :return: (String) directory name
        """
        if url is None:
            url = self.url
        name = url.split("/")[-1]
        name = name.split("?")[0]
        return " ".join(name.split("_")).title()

    def download(self, base_path=None, useproxy=False, options=None):  # noqa: C901
        """
        Download the YouTube resource(s) specified in `self.info`. If `self.info`
        is None, it will be populated by calling `self.get_resource_info` which
        in turn uses `self.url`. Returns None if download fails.
        """
        if base_path:
            download_dir = os.path.join(base_path, self.get_dir_name_from_url())
            utils.make_dir_if_needed(download_dir)
        else:
            download_dir = "."

        if self.client is None or self.info is None:
            # download should always be called after self.info is available
            self.get_resource_info()

        # Set reasonable default download options...
        self.client.params["outtmpl"] = "{}/%(id)s.%(ext)s".format(download_dir)
        self.client.params["writethumbnail"] = True  # TODO(ivan): revisit this
        self.client.params["continuedl"] = False  # clean start to avoid errors
        self.client.params["noprogress"] = True  # progressbar doesn't log well
        if options:
            # ...but override them based on user choices when specified
            self.client.params.update(options)
        LOGGER.debug("Using download options = {}".format(self.client.params))

        LOGGER.info("Downloading {} to dir {}".format(self.url, download_dir))
        for i in range(self.num_retries):

            # Proxy configuration for download (default = no proxy)
            if useproxy:
                # If useproxy ovverride specified, choose a new proxy server:
                dl_proxy = proxy.choose_proxy()
                self.client.params["proxy"] = dl_proxy
                self.client._setup_opener()  # this will re-initialize downloader
            elif (
                not useproxy
                and "proxy" in self.client.params
                and self.client.params["proxy"]
            ):
                # Disable proxy if it was used for the get_resource_info call
                self.client.params["proxy"] = None
                self.client._setup_opener()  # this will re-initialize downloader

            try:
                self.info = self.client.process_ie_result(self.info, download=True)
                LOGGER.debug("Finished process_ie_result successfully")
                break
            except Exception as e:
                network_related_error = True
                if isinstance(e, yt_dlp.utils.DownloadError):
                    (eclass, evalue, etraceback) = e.exc_info
                    if eclass in NON_NETWORK_ERRORS:
                        network_related_error = False
                if useproxy and network_related_error:
                    # Add the current proxy to the BROKEN_PROXIES list
                    proxy.record_error_for_proxy(dl_proxy, exception=e)
                if self.info:
                    # cleanup partially downloaded file to get a clean start
                    download_filename = self.client.prepare_filename(self.info)
                    if os.path.exists(download_filename):
                        os.remove(download_filename)
                LOGGER.warning(e)
                if i < self.num_retries - 1:
                    LOGGER.warning("Download {} failed, retrying...".format(i + 1))
                    time.sleep(self.sleep_seconds)

        # Post-process results
        # TODO(ivan): handle post processing filename when custom `outtmpl` specified in options
        if self.info:
            edited_results = self._format_for_ricecooker(self.info)
            if "children" in edited_results:
                for child in edited_results["children"]:
                    vfilename = "{}.{}".format(child["id"], child["ext"])
                    child["filename"] = os.path.join(download_dir, vfilename)
            else:
                vfilename = "{}.{}".format(edited_results["id"], edited_results["ext"])
                edited_results["filename"] = os.path.join(download_dir, vfilename)
            return edited_results
        else:
            return None

    def get_resource_subtitles(self, options=None):
        """
        Retrieves the subtitles for the video(s) represented by this resource.
        Subtitle information will be contained in the 'subtitles' key of the
        dictionary object returned.

        :return: A dictionary object that contains information about video subtitles
        """
        options_for_subtitles = dict(
            writesubtitles=True,  # extract subtitles info
            allsubtitles=True,  # get all available languages
            writeautomaticsub=False,  # do not include auto-generated subs
        )
        if options:
            options_for_subtitles.update(options)

        info = self.get_resource_info(options=options_for_subtitles)
        return info

    def _format_for_ricecooker(self, results):
        """
        Internal method for converting YouTube resource info into the format expected by ricecooker.

        :param results: YouTube resource dictionary object to be converted to ricecooker format.

        :return: A dictionary object in the format expected by ricecooker.
        """
        leaf = {}

        # dict mapping of field name and default value when not found.
        extracted_fields = {
            "id": "",
            "title": "",
            "description": "",
            "ext": "mp4",
            "thumbnail": "",
            "webpage_url": "",
            "tags": [],
            "subtitles": {},
            "requested_subtitles": "",
            "artist": "",
            "license": "",
            "_type": "video",
        }

        for field_name in extracted_fields:
            info_name = field_name
            if info_name == "_type":
                info_name = "kind"
            elif info_name == "webpage_url":
                info_name = "source_url"
            if field_name in results:
                leaf[info_name] = results[field_name]
            else:
                leaf[info_name] = extracted_fields[field_name]

        if "entries" in results:
            leaf["children"] = []
            for entry in results["entries"]:
                if entry is not None:
                    leaf["children"].append(self._format_for_ricecooker(entry))
                else:
                    LOGGER.info("Skipping None entry bcs failed extract info")

        return leaf

    def check_for_content_issues(self, filter=False):
        """
        Checks the YouTube resource and looks for any issues that may prevent download or distribution of the material,
        or would otherwise imply that the resource is not suitable for use in Kolibri.

        :param filter: If True, remove videos with issues from the returned resource info. Defaults to False.

        :return: A tuple containing a list of videos with waranings, and the resource info as a dictionary object.
        """
        resource_info = self.get_resource_info()
        output_video_info = copy.copy(resource_info)
        videos_with_warnings = []
        if filter:
            output_video_info["children"] = []

        for video in resource_info["children"]:
            warnings = []
            if not video["license"]:
                warnings.append("no_license_specified")
            elif video["license"].find("Creative Commons") == -1:
                warnings.append("closed_license")

            if len(warnings) > 0:
                videos_with_warnings.append({"video": video, "warnings": warnings})
            elif filter:
                output_video_info["children"].append(video)

        return videos_with_warnings, output_video_info


# YOUTUBE LANGUAGE CODE HELPERS
################################################################################


def get_language_with_alpha2_fallback(language_code):
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
    language_obj = get_language_with_alpha2_fallback(language)
    if language_obj is None:
        print("Found unsupported language code {}".format(language))
        return False
    else:
        return True


# CONSTANTS for YouTube cache
################################################################################
CHEFDATA_DIR = "chefdata"
DEFAULT_YOUTUBE_CACHE_DIR = os.path.join(CHEFDATA_DIR, "youtubecache")


# CONSTANTS for YouTube resources
################################################################################
YOUTUBE_VIDEO_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<youtube_id>[A-Za-z0-9\-=_]{11})"
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
        self.cache_dir = ""
        self.cache_path = ""
        self.url = ""

    def __str__(self):
        return "%s (%s)" % (self.type, self.cachename)

    def _get_youtube_info(self, use_proxy=True, use_cache=True, options=None):
        youtube_info = None
        # 1. Try to get from cache if allowed:
        if os.path.exists(self.cache_path) and use_cache:
            LOGGER.info("==> [%s] Retrieving cached information...", self.__str__())
            youtube_info = json.load(open(self.cache_path))
        # 2. Fetch info from yt_dlp
        if not youtube_info:
            LOGGER.info("==> [%s] Requesting info from youtube...", self.__str__())
            os.makedirs(self.cache_dir, exist_ok=True)
            try:
                youtube_resource = YouTubeResource(self.url, useproxy=use_proxy)
            except yt_dlp.utils.ExtractorError as e:
                if "unavailable" in str(e):
                    LOGGER.error(
                        "==> [%s] Resource unavailable for URL: %s",
                        self.__str__,
                        self.url,
                    )
                    return None

            if youtube_resource:
                try:
                    # Save YouTube info to JSON cache file
                    youtube_info = youtube_resource.get_resource_info(options)
                    if youtube_info:
                        json.dump(
                            youtube_info,
                            open(self.cache_path, "w"),
                            indent=4,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                    else:
                        LOGGER.error(
                            "==> [%s] Failed to extract YouTube info", self.__str__()
                        )
                except Exception as e:
                    LOGGER.error(
                        "==> [%s] Failed to get YouTube info: %s", self.__str__(), e
                    )
                    return None
        return youtube_info


class YouTubeVideoUtils(YouTubeUtils):
    def __init_subclass__(cls):
        return super().__init_subclass__()

    def __init__(self, id, alias="", cache_dir=""):
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
        self.cache_path = os.path.join(self.cache_dir, self.cachename + ".json")

    def get_video_info(
        self, use_proxy=True, use_cache=True, get_subtitle_languages=False, options=None
    ):
        """
        Get YouTube video info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get video info from local JSON cache, default to True
        :param get_subtitle_languages: Define if need to get info as available subtitle languages, default to False
        :param options: Additional options for yt_dlp.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/yt_dlp/YoutubeDL.py
        :return: A ricecooker-like info dict info about the video or None if extraction fails
        """
        extract_options = dict()
        if get_subtitle_languages:
            options_for_subtitles = dict(
                writesubtitles=True,  # extract subtitles info
                allsubtitles=True,  # get all available languages
                writeautomaticsub=False,  # do not include auto-generated subs
            )
            extract_options.update(options_for_subtitles)
        if options:
            extract_options.update(options)
        return self._get_youtube_info(
            use_proxy=use_proxy, use_cache=use_cache, options=extract_options
        )


class YouTubePlaylistUtils(YouTubeUtils):
    def __init__(self, id, alias="", cache_dir=""):
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
        self.cache_path = os.path.join(self.cache_dir, self.cachename + ".json")

    def get_playlist_info(
        self, use_proxy=True, use_cache=True, youtube_skip_download=True, options=None
    ):
        """
        Get YouTube playlist info by either requesting URL or extracting local cache
        :param use_cache: Define if allowed to get playlist info from local JSON cache, default to True
        :param youtube_skip_download: Skip the actual download of the YouTube video files
        :param options: Additional options for yt_dlp.
                        For full list of available options: https://github.com/ytdl-org/youtube-dl/blob/master/yt_dlp/YoutubeDL.py
        :return: A ricecooker-like info dict info about the playlist or None if extraction fails
        """
        youtube_extract_options = dict(
            skip_download=youtube_skip_download, extract_flat=True
        )
        if options:
            youtube_extract_options.update(options)
        return self._get_youtube_info(
            use_proxy=use_proxy, use_cache=use_cache, options=youtube_extract_options
        )
