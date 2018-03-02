import os
import re
import requests
import time
from urllib.parse import urlparse, parse_qs
import uuid

from bs4 import BeautifulSoup
from selenium import webdriver
from requests_file import FileAdapter
from ricecooker.config import PHANTOMJS_PATH
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter

DOWNLOAD_SESSION = requests.Session()                          # Session for downloading content from urls
DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
DOWNLOAD_SESSION.mount('file://', FileAdapter())
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

DOWNLOAD_SESSION.mount('http://', forever_adapter)
DOWNLOAD_SESSION.mount('https://', forever_adapter)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}


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
            if PHANTOMJS_PATH:
                driver = driver or webdriver.PhantomJS(executable_path=PHANTOMJS_PATH)
            else:
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


def make_request(url, clear_cookies=True, timeout=60, *args, **kwargs):
    sess = DOWNLOAD_SESSION

    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = sess.get(url, headers=headers, timeout=timeout, *args, **kwargs)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            retry_count += 1
            print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                return Dummy404ResponseObject(url=url)

    if response.status_code != 200:
        print("NOT FOUND:", url)

    return response


_CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")


def download_static_assets(doc, destination, base_url,
        request_fn=make_request, url_blacklist=[], js_middleware=None,
        css_middleware=None):
    """Download all static assets referenced from an HTML page.

    The goal is to easily create HTML5 apps! Downloads JS, CSS, images, and
    audio clips.

    doc: The HTML page source as a string or BeautifulSoup instance.
    destination: The folder to download the static assets to!
    base_url: The base URL where assets will be downloaded from.
    request_fn: The function to be called to make requests, passed to
        ricecooker.utils.html.download_file(). Pass in a custom one for custom
        caching logic.
    url_blacklist: A list of keywords of files to not include in downloading.
        Will do substring matching, so e.g. 'acorn.js' will match
        '/some/path/to/acorn.js'.
    js_middleware: If specificed, JS content will be passed into this callback
        which is expected to return JS content with any modifications.
    css_middleware: If specificed, CSS content will be passed into this callback
        which is expected to return CSS content with any modifications.

    Return the modified page HTML with links rewritten to the locations of the
    downloaded static files, as a BeautifulSoup object. (Call str() on it to
    extract the raw HTML.)
    """
    if not isinstance(doc, BeautifulSoup):
        doc = BeautifulSoup(doc, "html.parser")

    # Helper function to download all assets for a given CSS selector.
    def download_assets(selector, attr, url_middleware=None,
            content_middleware=None, node_filter=None):
        nodes = doc.select(selector)

        for i, node in enumerate(nodes):

            if node_filter:
                if not node_filter(node):
                    src = node[attr]
                    node[attr] = ''
                    print('        Skipping node with src ', src)
                    continue

            url = make_fully_qualified_url(node[attr], base_url)

            if _is_blacklisted(url, url_blacklist):
                print('        Skipping downloading blacklisted url', url)
                node[attr] = ""
                continue

            if url_middleware:
                url = url_middleware(url)

            filename = _derive_filename(url)
            node[attr] = filename

            print("        Downloading", url, "to filename", filename)
            download_file(url, destination, request_fn=make_request,
                    filename=filename, middleware_callbacks=content_middleware)

    def js_content_middleware(content, url, **kwargs):
        if js_middleware:
            content = js_middleware(content, url, **kwargs)

        # Polyfill localStorage and document.cookie as iframes can't access
        # them
        return (content
            .replace("localStorage", "_localStorage")
            .replace('document.cookie.split', '"".split')
            .replace('document.cookie', 'window._document_cookie'))

    def css_node_filter(node):
        return "stylesheet" in node["rel"]

    def css_content_middleware(content, url, **kwargs):
        if css_middleware:
            content = css_middleware(content, url, **kwargs)

        file_dir = os.path.dirname(urlparse(url).path)

        # Download linked fonts and images
        def repl(match):
            src = match.group(1)
            if src.startswith('//localhost'):
                return 'url()'
            # Don't download data: files
            if src.startswith('data:'):
                return match.group(0)
            src_url = make_fully_qualified_url(os.path.join(file_dir, src), base_url)

            if _is_blacklisted(src_url, url_blacklist):
                print('        Skipping downloading blacklisted url', src_url)
                return 'url()'

            derived_filename = _derive_filename(src_url)
            download_file(src_url, destination, request_fn=make_request,
                    filename=derived_filename)
            return 'url("%s")' % derived_filename

        return _CSS_URL_RE.sub(repl, content)

    # Download all linked static assets.
    download_assets("img[src]", "src")  # Images
    download_assets("link[href]", "href",
            content_middleware=css_content_middleware,
            node_filter=css_node_filter)  # CSS
    download_assets("script[src]", "src",
            content_middleware=js_content_middleware) # JS
    download_assets("source[src]", "src") # Potentially audio
    download_assets("source[srcset]", "srcset") # Potentially audio

    # ... and also run the middleware on CSS/JS embedded in the page source to
    # get linked files.
    for node in doc.select('style'):
        node.string = css_content_middleware(node.get_text(), url='')

    for node in doc.select('script'):
        if not node.attrs.get('src'):
            node.string = js_content_middleware(node.get_text(), url='')

    return doc


def _is_blacklisted(url, url_blacklist):
    return any((item in url.lower()) for item in url_blacklist)


# TODO(davidhu): Use MD5 hash of URL (ideally file) instead.
def _derive_filename(url):
    name = os.path.basename(urlparse(url).path).replace('%', '_')
    return ("%s.%s" % (uuid.uuid4().hex, name)).lower()


def make_fully_qualified_url(url, base):
    # TODO(davidhu): This is some hacky special-casing for 3asafeer ...
    if url.startswith("../images"):
        return base + url[2:]
    if url.startswith("../scripts"):
        return base + url[2:]
    if url.startswith("//"):
        return "http:" + url
    if url.startswith("/"):
        return base + url
    if not url.startswith("http"):
        return "%s/%s" % (base, url)
    return url
