import requests
import time
from selenium import webdriver
from requests_file import FileAdapter
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter

DOWNLOAD_SESSION = requests.Session()                          # Session for downloading content from urls
DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
DOWNLOAD_SESSION.mount('file://', FileAdapter())
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

DOWNLOAD_SESSION.mount('http://', forever_adapter)
DOWNLOAD_SESSION.mount('https://', forever_adapter)


def read(path, loadjs=False, session=None, driver=None):
    """ read: Reads from source and returns contents
        Args:
            path: (str) url or local path to download
            loadjs: (boolean) indicates whether to load js (optional)
            session: (requests.Session) session to use to download (optional)
            driver: (selenium.webdriver) webdriver to use to download (optional)
        Returns: str content from file or page
    """
    session = session or DOWNLOAD_SESSION
    try:
        if loadjs:                                              # Wait until js loads then return contents
            driver = driver or webdriver.PhantomJS()
            driver.get(path)
            time.sleep(5)
            return driver.page_source
        else:                                                   # Read page contents from url
            response = DOWNLOAD_SESSION.get(path, stream=True)
            response.raise_for_status()
            return response.content
    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
        with open(path, 'rb') as fobj:                          # If path is a local file path, try to open the file
            return fobj.read()
