import copy
import os
import re
import requests
import time
from urllib.parse import urlparse, urljoin
import uuid

from bs4 import BeautifulSoup
from selenium import webdriver
import selenium.webdriver.support.ui as selenium_ui
from requests_file import FileAdapter
from ricecooker.config import LOGGER, PHANTOMJS_PATH
from ricecooker.utils.html import download_file
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter

DOWNLOAD_SESSION = requests.Session()                          # Session for downloading content from urls
DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
DOWNLOAD_SESSION.mount('file://', FileAdapter())
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

DOWNLOAD_SESSION.mount('http://', forever_adapter)
DOWNLOAD_SESSION.mount('https://', forever_adapter)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}


USE_PYPPETEER = False

try:
    import asyncio
    from pyppeteer import launch

    async def load_page(path):
        browser = await launch({'headless': True})
        page = await browser.newPage()
        await page.goto(path, waitUntil='load')
        # get the entire rendered page, including the doctype
        content = await page.content()
        cookies = await page.cookies()
        await browser.close()
        return content, {'cookies': cookies}
    USE_PYPPETEER = True
except:
    print("Unable to load pyppeteer, using phantomjs for JS loading.")
    pass


def read(path, loadjs=False, session=None, driver=None, timeout=60,
        clear_cookies=True, loadjs_wait_time=3, loadjs_wait_for_callback=None):
    """Reads from source and returns contents

    Args:
        path: (str) url or local path to download
        loadjs: (boolean) indicates whether to load js (optional)
        session: (requests.Session) session to use to download (optional)
        driver: (selenium.webdriver) webdriver to use to download (optional)
        timeout: (int) Maximum number of seconds to wait for the request to complete.
        clear_cookies: (boolean) whether to clear cookies.
        loadjs_wait_time: (int) if loading JS, seconds to wait after the
            page has loaded before grabbing the page source
        loadjs_wait_for_callback: (function<selenium.webdriver>) if loading
            JS, a callback that will be invoked to determine when we can
            grab the page source. The callback will be called with the
            webdriver, and should return True when we're ready to grab the
            page source. For example, pass in an argument like:
            ``lambda driver: driver.find_element_by_id('list-container')``
            to wait for the #list-container element to be present before rendering.
    Returns: str content from file or page
    """
    session = session or DOWNLOAD_SESSION

    if clear_cookies:
        session.cookies.clear()

    try:
        if loadjs:                                              # Wait until js loads then return contents
            if USE_PYPPETEER:
                content = asyncio.get_event_loop().run_until_complete(load_page(path))
                return content

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
                    response = session.get(path, stream=True, timeout=timeout)
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


def make_request(url, clear_cookies=False, headers=None, timeout=60, *args, **kwargs):
    sess = DOWNLOAD_SESSION

    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    request_headers = DEFAULT_HEADERS
    if headers:
        request_headers = copy.copy(DEFAULT_HEADERS)
        request_headers.update(headers)

    while True:
        try:
            response = sess.get(url, headers=request_headers, timeout=timeout, *args, **kwargs)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            retry_count += 1
            print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                raise e

    if response.status_code != 200:
        print("NOT FOUND:", url)

    return response


_CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")


# TODO(davidhu): Use MD5 hash of URL (ideally file) instead.
def _derive_filename(url):
    name = os.path.basename(urlparse(url).path).replace('%', '_')
    return ("%s.%s" % (uuid.uuid4().hex, name)).lower()


def download_static_assets(doc, destination, base_url,
        request_fn=make_request, url_blacklist=[], js_middleware=None,
        css_middleware=None, derive_filename=_derive_filename):
    """
    Download all static assets referenced from an HTML page.
    The goal is to easily create HTML5 apps! Downloads JS, CSS, images, and
    audio clips.

    Args:
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

            if node[attr].startswith('data:'):
                continue

            url = urljoin(base_url, node[attr])

            if _is_blacklisted(url, url_blacklist):
                print('        Skipping downloading blacklisted url', url)
                node[attr] = ""
                continue

            if url_middleware:
                url = url_middleware(url)

            filename = derive_filename(url)
            node[attr] = filename

            print("        Downloading", url, "to filename", filename)
            download_file(url, destination, request_fn=request_fn,
                    filename=filename, middleware_callbacks=content_middleware)

    def js_content_middleware(content, url, **kwargs):
        if js_middleware:
            content = js_middleware(content, url, **kwargs)
        return content

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
            src_url = urljoin(base_url, os.path.join(file_dir, src))

            if _is_blacklisted(src_url, url_blacklist):
                print('        Skipping downloading blacklisted url', src_url)
                return 'url()'

            derived_filename = derive_filename(src_url)
            download_file(src_url, destination, request_fn=request_fn,
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

def archive_page(url, download_root):
    """
    Download fully rendered page and all related assets into ricecooker's site archive format.

    :param url: URL to download
    :param download_root: Site archive root directory
    :return: A dict containing info about the page archive operation
    """

    os.makedirs(download_root, exist_ok=True)
    content, props = asyncio.get_event_loop().run_until_complete(load_page(url))

    parsed_url = urlparse(url)
    page_domain = parsed_url.netloc.replace(':', '_')

    # get related assets
    base_url = url[:url.rfind('/')]
    urls_to_replace = {}
    def html5_derive_filename(url):
        file_url_parsed = urlparse(url)

        no_scheme_url = url
        if file_url_parsed.scheme != '':
            no_scheme_url = url.replace(file_url_parsed.scheme + '://', '')
        rel_path = file_url_parsed.path.replace('%', '_')
        domain = file_url_parsed.netloc.replace(':', '_')
        if not domain:
            domain = page_domain
        if rel_path.startswith('/'):
            rel_path = rel_path[1:]
        url_local_dir = os.path.join(domain, rel_path)
        assert domain in url_local_dir
        local_dir_name = os.path.dirname(url_local_dir)
        if local_dir_name != url_local_dir:
            full_dir = os.path.join(download_root, local_dir_name)
            os.makedirs(full_dir, exist_ok=True)
            urls_to_replace[url] = no_scheme_url
        return url_local_dir

    if content:
        download_static_assets(content, download_root, base_url, derive_filename=html5_derive_filename)

        for key in urls_to_replace:
            url_parts = urlparse(key)
            # When we get an absolute URL, it may appear in one of three different ways in the page:
            key_variants = [
                # 1. /path/to/file.html
                key.replace(url_parts.scheme + '://' + url_parts.netloc, ''),
                # 2. https://www.domain.com/path/to/file.html
                key,
                # 3. //www.domain.com/path/to/file.html
                key.replace(url_parts.scheme + ':', ''),
            ]

            orig_content = content
            for variant in key_variants:
                # searching within quotes ensures we only replace the exact URL we are
                # trying to replace
                # we avoid using BeautifulSoup because Python HTML parsers can be destructive and
                # do things like strip out the doctype.
                content = content.replace('="{}"'.format(variant), '="{}"'.format(urls_to_replace[key]))
                content = content.replace('url({})"'.format(variant), 'url({})'.format(urls_to_replace[key]))

            if content == orig_content:
                LOGGER.debug("link not replaced: {}".format(key))
                LOGGER.debug("key_variants = {}".format(key_variants))

        download_dir = os.path.join(page_domain, parsed_url.path.split('/')[-1].replace('?', '_'))
        download_path = os.path.join(download_root, download_dir)
        os.makedirs(download_path, exist_ok=True)

        index_path = os.path.join(download_path, 'index.html')
        f = open(index_path, 'w', encoding='utf-8')
        f.write(content)
        f.close()

        page_info = {
            'url': url,
            'cookies': props['cookies'],
            'index_path': index_path,
            'resources': list(urls_to_replace.values())
        }

        return page_info

    return None


def _is_blacklisted(url, url_blacklist):
    return any((item in url.lower()) for item in url_blacklist)
