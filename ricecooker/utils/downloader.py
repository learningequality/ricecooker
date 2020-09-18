import copy
import mimetypes
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
        return content, {'cookies': cookies, 'url': page.url}
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


# global to track URLs already downloaded, so we don't keep downloading the same content over and over
# because it's referenced in many different places
downloaded_links = []


def download_static_assets(doc, destination, base_url,
        request_fn=make_request, url_blacklist=[], js_middleware=None,
        css_middleware=None, derive_filename=_derive_filename, link_policy=None):
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
    # without the ending /, some functions will treat the last path component like a filename, so add it.
    if not base_url.endswith('/'):
        base_url += '/'

    LOGGER.warning("base_url = {}".format(base_url))

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
                LOGGER.info('        Skipping downloading blacklisted url', url)
                node[attr] = ""
                continue

            if url_middleware:
                url = url_middleware(url)

            filename = derive_filename(url)
            _path, ext = os.path.splitext(filename)
            subpath = None
            if not ext:
                # This COULD be an index file in a dir, or just a file with no extension. Handle either case by
                # turning the path into filename + '/index' + the file extension from the content type
                response = requests.get(url)
                type = response.headers['content-type'].split(';')[0]
                ext = mimetypes.guess_extension(type)
                # if we're really stuck, just default to HTML as that is most likely if this is a redirect.
                if not ext:
                    ext = '.html'
                subpath = os.path.dirname(filename)
                filename = 'index{}'.format(ext)

                os.makedirs(os.path.join(destination, subpath), exist_ok=True)

            node[attr] = filename

            LOGGER.info("Downloading {} to filename {}".format(url, filename))
            download_file(url, destination, request_fn=request_fn,
                    filename=filename, subpath=subpath, middleware_callbacks=content_middleware)

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
            return 'url("%s")' % src

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

    # Link scraping can be expensive, so it's off by default. We decrement the levels value every time we recurse
    # so skip once we hit zero.
    if link_policy is not None and link_policy['levels'] > 0:
        nodes = doc.select("iframe[src]")
        # TODO: add "a[href]" handling to this and/or ways to whitelist / blacklist tags and urls
        for node in nodes:

            url = node['src']
            parts = urlparse(url)
            should_scrape = False
            if not parts.scheme or parts.scheme.startswith('http'):
                if not parts.netloc or parts.netloc in base_url:
                    should_scrape = link_policy['scope'] in ['same_domain', 'all']
                    if not parts.netloc:
                        url = urljoin(base_url, url)
                        LOGGER.warning("url = {}".format(url))
                else:
                    should_scrape = link_policy['scope'] in ['external', 'all']

            if should_scrape and not url in downloaded_links:
                LOGGER.info("Scraping link, policy is: {}".format(link_policy))
                # we need to use archive_page because the iframe may have its own set of assets
                LOGGER.info("Downloading iframe to {}: {}".format(url, destination))
                policy = copy.copy(link_policy)
                # make sure we reduce the depth level by one each time we recurse
                policy['levels'] -= 1
                archive_page(url, destination, link_policy)
                downloaded_links.append(url)

    # ... and also run the middleware on CSS/JS embedded in the page source to
    # get linked files.
    for node in doc.select('style'):
        node.string = css_content_middleware(node.get_text(), url='')

    for node in doc.select('script'):
        if not node.attrs.get('src'):
            node.string = js_content_middleware(node.get_text(), url='')

    return doc

def archive_page(url, download_root, link_policy=None, run_js=False):
    """
    Download fully rendered page and all related assets into ricecooker's site archive format.

    :param url: URL to download
    :param download_root: Site archive root directory
    :param link_policy: a dict of the following policy, or None to ignore all links.
            key: policy, value: string, one of "scrape" or "ignore"
            key: scope, value: string, one of "same_domain", "external", "all"
            key: levels, value: integer, number of levels deep to apply this policy

    :return: A dict containing info about the page archive operation
    """

    os.makedirs(download_root, exist_ok=True)
    if run_js:
        content, props = asyncio.get_event_loop().run_until_complete(load_page(url))
    else:
        retry_count = 0
        max_retries = 5
        while True:
            try:
                response = DOWNLOAD_SESSION.get(url, stream=True, timeout=60000)
                props = {'cookies': requests.utils.dict_from_cookiejar(response.cookies), 'url': response.url}
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
                retry_count += 1
                print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                      .format(msg=str(e), count=retry_count, trymax=max_retries))
                time.sleep(retry_count * 1)
                if retry_count >= max_retries:
                    raise e

        response.raise_for_status()
        content = response.text


    LOGGER.warning("Props = {}".format(props))

    # url may be redirected, for relative link handling we want the final URL that was loaded.
    url = props['url']
    parsed_url = urlparse(url)
    page_domain = parsed_url.netloc.replace(':', '_')

    # get related assets
    base_url = url[:url.rfind('/')]
    urls_to_replace = {}
    def html5_derive_filename(url):
        LOGGER.warning("url = {}".format(url))
        file_url_parsed = urlparse(url)

        no_scheme_url = url
        if file_url_parsed.scheme != '':
            no_scheme_url = url.replace(file_url_parsed.scheme + '://', '')
        rel_path = file_url_parsed.path.replace('%', '_')
        domain = file_url_parsed.netloc.replace(':', '_')
        if not domain:
            domain = page_domain
            if rel_path.startswith('/') and not url.startswith('/'):
                # urlparse assumes links that are relative are relative to the domain root, which is not
                # a safe assumption. Just use the original passed in URL for further processing.
                rel_path = url
        if rel_path.startswith('/'):
            rel_path = rel_path[1:]
        else:
            # it is relative to the current subdir, not the root of the domain
            if parsed_url.path.endswith('/'):
                rel_path = parsed_url.path + rel_path
            else:
                rel_path = os.path.dirname(parsed_url.path) + '/' + rel_path
        url_local_dir = os.path.join(domain, rel_path)
        assert domain in url_local_dir
        LOGGER.warning("rel_path = {}, parsed_url_path = {}".format(rel_path, parsed_url.path))
        LOGGER.warning("local_dir_name = {}".format(url_local_dir))

        _path, ext = os.path.splitext(url_local_dir)
        local_dir_name = url_local_dir
        if ext != '':
            local_dir_name = os.path.dirname(url_local_dir)
        if local_dir_name != url_local_dir:
            full_dir = os.path.join(download_root, local_dir_name)
            os.makedirs(full_dir, exist_ok=True)
            urls_to_replace[url] = no_scheme_url
        return url_local_dir

    if content:
        LOGGER.warning("Downloading assets for {}".format(url))
        download_static_assets(content, download_root, base_url, derive_filename=html5_derive_filename,
                               link_policy=link_policy)

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
                old_str = '="{}"'.format(variant)
                new_str = '="{}"'.format(urls_to_replace[key])
                content = content.replace(old_str, new_str)
                # content = content.replace('url({})"'.format(variant), 'url({})'.format(urls_to_replace[key]))

            if content == orig_content:
                LOGGER.debug("link not replaced: {}".format(key))
                LOGGER.debug("key_variants = {}".format(key_variants))

        download_path = os.path.join(download_root, html5_derive_filename(parsed_url.path))
        _path, ext = os.path.splitext(download_path)
        index_path = download_path
        if '.htm' not in ext:
            index_path = os.path.join(download_path, 'index.html')

        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        soup = BeautifulSoup(content)
        f = open(index_path, 'wb')
        f.write(soup.prettify(encoding="utf-8"))
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
