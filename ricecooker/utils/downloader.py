import requests
import time
from selenium import webdriver
import selenium.webdriver.support.ui as selenium_ui
from requests_file import FileAdapter
from ricecooker.config import PHANTOMJS_PATH
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter

DOWNLOAD_SESSION = requests.Session()                          # Session for downloading content from urls
DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
DOWNLOAD_SESSION.mount('file://', FileAdapter())
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

DOWNLOAD_SESSION.mount('http://', forever_adapter)
DOWNLOAD_SESSION.mount('https://', forever_adapter)


def read(path, loadjs=False, session=None, driver=None, timeout=60,
        clear_cookies=True, loadjs_wait_time=3, loadjs_wait_for_callback=None):
    """ read: Reads from source and returns contents
        Args:
            path: (str) url or local path to download
            loadjs: (boolean) indicates whether to load js (optional)
            session: (requests.Session) session to use to download (optional)
            driver: (selenium.webdriver) webdriver to use to download (optional)
            timeout: (int) Maximum number of seconds to wait for the request to
                complete.
            clear_cookies: (boolean) whether to clear cookies.
            loadjs_wait_time: (int) if loading JS, seconds to wait after the
                page has loaded before grabbing the page source
            loadjs_wait_for_callback: (function<selenium.webdriver>) if loading
                JS, a callback that will be invoked to determine when we can
                grab the page source. The callback will be called with the
                webdriver, and should return True when we're ready to grab the
                page source. For example, pass in an argument like:
                    lambda driver: driver.find_element_by_id('list-container')
                to wait for the #list-container element to be present before
                rendering.
        Returns: str content from file or page
    """
    session = session or DOWNLOAD_SESSION

    if clear_cookies:
        session.cookies.clear()

    try:
        if loadjs:                                              # Wait until js loads then return contents
            if PHANTOMJS_PATH:
                driver = driver or webdriver.PhantomJS(executable_path=PHANTOMJS_PATH)
            else:
                driver = driver or webdriver.PhantomJS()
            driver.get(path)
            if loadjs_wait_for_callback:
                selenium_ui.WebDriverWait(driver, 60).until(loadjs_wait_for_callback)
            time.sleep(loadjs_wait_time)
            return driver.page_source

        else:                                                   # Read page contents from url
            retry_count = 0
            max_retries = 5
            while True:
                try:
                    response = DOWNLOAD_SESSION.get(path, stream=True, timeout=timeout)
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
                    retry_count += 1
                    print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                        .format(msg=str(e), count=retry_count, trymax=max_retries))
                    time.sleep(retry_count * 1)
                    if retry_count >= max_retries:
                        raise e

            response.raise_for_status()
            return response.content

    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
        with open(path, 'rb') as fobj:                          # If path is a local file path, try to open the file
            return fobj.read()
