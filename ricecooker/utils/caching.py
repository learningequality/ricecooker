from datetime import datetime
from datetime import timedelta
from email.utils import parsedate  # noqa: F401

import cachecontrol  # noqa: F401
import requests  # noqa: F401
from cachecontrol import CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache  # noqa: F401
from cachecontrol.heuristics import BaseHeuristic
from cachecontrol.heuristics import datetime_to_header
from cachecontrol.heuristics import expire_after


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
