import json
import os
from datetime import datetime
from datetime import timedelta

from cachecontrol import CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import BaseHeuristic
from cachecontrol.heuristics import datetime_to_header
from cachecontrol.heuristics import expire_after

from ricecooker import config
from ricecooker.utils.utils import get_hash
from ricecooker.utils.utils import is_valid_url


# Cache for filenames
FILECACHE = FileCache(config.FILECACHE_DIRECTORY, forever=True)


class NeverCache(BaseHeuristic):
    """
    Don't cache the response at all.
    """

    def update_headers(self, response):
        return {"cache-control": "no-cache"}


class CacheForeverHeuristic(BaseHeuristic):
    """
    Cache the response effectively forever.
    """

    def update_headers(self, response):
        headers = {}
        expires = expire_after(timedelta(weeks=10 * 52), date=datetime.now())
        headers["expires"] = datetime_to_header(expires)
        headers["cache-control"] = "public"

        return headers


class InvalidatingCacheControlAdapter(CacheControlAdapter):
    """
    Cache control adapter that deletes items from the cache as they're requested.
    Default heuristic is also set to a non-caching heuristic.
    """

    def __init__(self, heuristic=None, *args, **kw):
        if not heuristic:
            heuristic = NeverCache()
        super(InvalidatingCacheControlAdapter, self).__init__(
            *args, heuristic=heuristic, **kw
        )

    def send(self, request, **kw):

        # delete any existing cached value from the cache
        try:
            cache_url = self.controller.cache_url(request.url)
            self.cache.delete(cache_url)
        except FileNotFoundError:
            pass

        resp = super(InvalidatingCacheControlAdapter, self).send(request, **kw)

        return resp


def generate_key(action, path_or_id, settings=None, default=" (default)"):
    """generate_key: generate key used for caching
    Args:
        action (str): how video is being processed (e.g. COMPRESSED or DOWNLOADED)
        path_or_id (str): path to video or youtube_id
        settings (dict): settings for compression or downloading passed in by user
        default (str): if settings are None, default to this extension (avoid overwriting keys)
    Returns: filename
    """
    if settings and "postprocessors" in settings:
        # get determinisic dict serialization for nested dicts under Python 3.5
        settings_str = json.dumps(settings, sort_keys=True)
    else:
        # keep using old strategy to avoid invalidating all chef caches
        settings_str = (
            "{}".format(str(sorted(settings.items()))) if settings else default
        )
    return "{}: {} {}".format(action.upper(), path_or_id, settings_str)


def set_cache_data(key, file_metadata):
    if not key:
        return None
    FILECACHE.set(key, bytes(json.dumps(file_metadata), "utf-8"))


def get_cache_data(key):
    if not key:
        return None
    file_metadata = FILECACHE.get(key)

    if not file_metadata:
        return None
    file_metadata = file_metadata.decode("utf-8")

    try:
        file_metadata = json.loads(file_metadata)
    except json.JSONDecodeError:
        file_metadata = {
            "filename": file_metadata,
        }
    if not os.path.exists(config.get_storage_path(file_metadata["filename"])):
        return None
    return file_metadata


def get_cache_filename(key):
    cache_file = get_cache_data(key)
    if not cache_file:
        return None
    return cache_file["filename"]


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
