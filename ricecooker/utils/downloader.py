import concurrent.futures
import copy
import json
import mimetypes
import os
import re
import requests
import shutil
import tempfile
import time
from urllib.parse import urlparse, urljoin
from urllib.request import url2pathname
import uuid

import chardet

from bs4 import BeautifulSoup
from selenium import webdriver
import selenium.webdriver.support.ui as selenium_ui
from requests_file import FileAdapter
from ricecooker.config import LOGGER, PHANTOMJS_PATH, STRICT
from ricecooker.utils.html import download_file, replace_links
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.zip import create_predictable_zip

DOWNLOAD_SESSION = requests.Session()                          # Session for downloading content from urls
DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
DOWNLOAD_SESSION.mount('file://', FileAdapter())
# use_dir_lock works with all filesystems and OSes
cache = FileCache('.webcache', use_dir_lock=True)
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

# we can't use requests caching for pyppeteer / phantomjs, so track those separately.
downloaded_pages = {}

DOWNLOAD_SESSION.mount('http://', forever_adapter)
DOWNLOAD_SESSION.mount('https://', forever_adapter)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}


USE_PYPPETEER = False

# HACK ALERT! This is to allow ArchiveDownloader to be used from within link scraping.
# Once this code stabilizes, we should refactor it so that all downloading is
# encapsulated into a class.
archiver = None

try:
    import asyncio
    from pyppeteer import launch, errors

    async def load_page(path, timeout=30, strict=True):
        browser = await launch({'headless': True})
        content = None
        cookies = None
        page = None
        try:
            page = await browser.newPage()
            try:
                await page.goto(path, {'timeout': timeout * 1000, 'waitUntil': ['load', 'domcontentloaded', 'networkidle0']})
            except errors.TimeoutError:
                # some sites have API calls running regularly, so the timeout may be that there's never any true
                # network idle time. Try 'networkidle2' option instead before determining we can't scrape.
                if not strict:
                    LOGGER.info("Attempting to download URL with networkidle2 instead of networkidle0...")
                    await page.goto(path, {'timeout': timeout * 1000, 'waitUntil': ['load', 'domcontentloaded', 'networkidle2']})
                else:
                    raise
            # get the entire rendered page, including the doctype
            content = await page.content()
            cookies = await page.cookies()
        except Exception as e:
            LOGGER.warning("Error scraping page: {}".format(e))
        finally:
            await browser.close()
        return content, {'cookies': cookies, 'url': path}

    async def take_screenshot(url, filename, element=None, timeout=30):
        browser = await launch({'headless': True})
        try:
            page = await browser.newPage()
            await page.goto(url,
                            {'timeout': timeout * 1000, 'waitUntil': ['load', 'domcontentloaded', 'networkidle0']})
            screenshot_element = page
            if element:
                await page.waitForSelector(element, {'timeout': 10000})
                elements = await page.querySelectorAll(element)
                if len(list(elements)) > 1:
                    LOGGER.warning("Multiple elements matched screenshot element, using first...")
                screenshot_element = elements[0]

            LOGGER.info("Saving screenshot to {}".format(filename))
            await screenshot_element.screenshot({'path': filename})

        finally:
            await page.close()
            await browser.close()
    USE_PYPPETEER = True
except:
    print("Unable to load pyppeteer, using phantomjs for JS loading.")
    pass


def read(path, loadjs=False, session=None, driver=None, timeout=60,
        clear_cookies=True, loadjs_wait_time=3, loadjs_wait_for_callback=None, strict=True):
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
        strict: (bool) If False, when download fails, retry but allow parsing even if there
            is still minimal network traffic happening. Useful for sites that regularly poll APIs.
    Returns: str content from file or page
    """
    session = session or DOWNLOAD_SESSION

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
            response = make_request(path, clear_cookies, session=session)

            return response.content

    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
        with open(path, 'rb') as fobj:                          # If path is a local file path, try to open the file
            return fobj.read()


def make_request(url, clear_cookies=False, headers=None, timeout=60, session=None, *args, **kwargs):
    sess = session or DOWNLOAD_SESSION

    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    request_headers = DEFAULT_HEADERS
    if headers:
        request_headers = copy.copy(DEFAULT_HEADERS)
        request_headers.update(headers)

    while retry_count <= max_retries:
        try:
            response = sess.get(url, headers=request_headers, stream=True, timeout=timeout, *args, **kwargs)
            if response.status_code != 200:
                LOGGER.error("{} error while trying to download {}".format(response.status_code, url))
                if STRICT:
                    response.raise_for_status()
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            retry_count += 1
            LOGGER.warning("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count > max_retries:
                LOGGER.error("Could not connect to: {}".format(url))
                if STRICT:
                    raise e
    return None


_CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")


# TODO(davidhu): Use MD5 hash of URL (ideally file) instead.
def _derive_filename(url):
    name = os.path.basename(urlparse(url).path).replace('%', '_')
    return ("%s.%s" % (uuid.uuid4().hex, name)).lower()


# TODO: The number of args and inner functions in this strongly suggest this needs
# to be a class or have its functionality separated out.
def download_static_assets(doc, destination, base_url,
        request_fn=make_request, url_blacklist=[], js_middleware=None,
        css_middleware=None, derive_filename=_derive_filename, link_policy=None,
        run_js=False, resource_urls=None, relative_links=False):
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

    LOGGER.debug("base_url = {}".format(base_url))

    if not isinstance(doc, BeautifulSoup):
        doc = BeautifulSoup(doc, "lxml")

    def download_srcset(selector, attr, content_middleware=None):
        nodes = doc.select(selector)

        for i, node in enumerate(nodes):
            srcset = node[attr]
            sources = srcset.split(',')
            new_sources = []
            for source in sources:
                # a source can be just a URL, or a URL + a space character and then a width or resolution.
                parts = source.split(" ")
                url = urljoin(base_url, parts[0])
                filename = derive_filename(url)
                new_url = filename
                if relative_links and base_url:
                    base_filename = derive_filename(base_url)
                    new_url = get_relative_url_for_archive_filename(filename, base_filename)

                fullpath = os.path.join(destination, filename)
                if not os.path.exists(fullpath):
                    LOGGER.info("Downloading {} to filename {}".format(url, fullpath))
                    download_file(url, destination, request_fn=request_fn,
                                  filename=filename, middleware_callbacks=content_middleware)
                if len(parts) > 1:
                    new_sources.append(" ".join([new_url,  parts[1]]))
                else:
                    new_sources.append(new_url)
            node[attr] = ', '.join(new_sources)

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

            new_url = filename
            if relative_links and base_url:
                base_filename = get_archive_filename(base_url)
                new_url = get_relative_url_for_archive_filename(filename, base_filename)
            node[attr] = new_url

            fullpath = os.path.join(destination, filename)
            if not os.path.exists(fullpath):
                LOGGER.info("Downloading {} to filename {}".format(url, fullpath))
                download_file(url, destination, request_fn=request_fn,
                    filename=filename, middleware_callbacks=content_middleware)
            elif content_middleware:
                # Make sure we run middleware, as it creates a list of file dependencies that we need when
                # converting the content into a zip file.
                # TODO: We should probably separate out the download step from the middleware step, so
                # that middleware can be run regardless of how we get the content.
                content = open(fullpath, 'r', encoding='utf-8').read()
                new_content = content_middleware(content, url)
                if new_content != content:
                    # if the middleware changed the content, update it.
                    with open(fullpath, 'w') as f:
                        f.write(new_content)


    def js_content_middleware(content, url, **kwargs):
        if js_middleware:
            content = js_middleware(content, url, **kwargs)
        return content

    def css_node_filter(node):
        if "rel" in node:
            return "stylesheet" in node["rel"]
        return node["href"].split("?")[0].strip().endswith(".css")

    def css_content_middleware(content, url, **kwargs):
        if css_middleware:
            content = css_middleware(content, url, **kwargs)

        root_parts = urlparse(url)

        # Download linked fonts and images
        def repl(match):
            src = match.group(1)

            if src.startswith('//localhost'):
                return 'url()'
            # Don't download data: files
            if src.startswith('data:'):
                return match.group(0)
            parts = urlparse(src)
            root_url = None
            if url:
                root_url = url[:url.rfind('/') + 1]

            if parts.scheme and parts.netloc:
                src_url = src
            elif parts.path.startswith('/') and url:
                src_url = '{}://{}{}'.format(root_parts.scheme, root_parts.netloc, parts.path)
            elif url and root_url:
                src_url = urljoin(root_url, src)
            else:
                src_url = urljoin(base_url, src)

            if _is_blacklisted(src_url, url_blacklist):
                print('        Skipping downloading blacklisted url', src_url)
                return 'url()'

            derived_filename = derive_filename(src_url)

            new_url = src
            if url and parts.path.startswith('/') or relative_links:
                page_filename = derive_filename(url)
                new_url = get_relative_url_for_archive_filename(derived_filename, page_filename)
            elif derive_filename == _derive_filename:
                # The _derive_filename function puts all files in the root, so all URLs need
                # rewritten. When using get_archive_filename, relative URLs will still work.
                new_url = derived_filename

            fullpath = os.path.join(destination, derived_filename)
            if not os.path.exists(fullpath):
                download_file(src_url, destination, request_fn=request_fn,
                    filename=derived_filename)
            else:
                LOGGER.debug("Resource already downloaded, skipping: {}".format(src_url))
            return 'url("%s")' % new_url

        return _CSS_URL_RE.sub(repl, content)

    # Download all linked static assets.
    download_assets("img[src]", "src")  # Images
    download_srcset("img[srcset]", "srcset")  # Images
    download_assets("link[href]", "href",
            content_middleware=css_content_middleware,
            node_filter=css_node_filter)  # CSS
    download_assets("script[src]", "src",
            content_middleware=js_content_middleware) # JS
    download_assets("source[src]", "src") # Potentially audio
    download_srcset("source[srcset]", "srcset") # Potentially audio

    # Link scraping can be expensive, so it's off by default. We decrement the levels value every time we recurse
    # so skip once we hit zero.
    if link_policy is not None and link_policy['levels'] > 0:
        nodes = doc.select("iframe[src]")
        nodes += doc.select("a[href]")
        # TODO: add "a[href]" handling to this and/or ways to whitelist / blacklist tags and urls
        for node in nodes:
            url = None
            if node.name == 'iframe':
                url = node['src']
            elif node.name == 'a':
                url = node['href']
            assert url is not None
            download_url = url.split('#')[0]  # Ignore bookmarks in URL
            if download_url.strip() == "":
                continue
            parts = urlparse(download_url)
            # if we're scraping links, always scrape relative links regardless of setting.
            should_scrape = 'all' in link_policy['scope'] or (not parts.scheme and not parts.netloc)
            if not parts.scheme or parts.scheme.startswith('http'):
                LOGGER.debug("checking url: {}".format(url))
                if not parts.netloc:
                    download_url = urljoin(base_url, download_url)
                if 'whitelist' in link_policy:
                    for whitelist_item in link_policy['whitelist']:
                        if whitelist_item in download_url:
                            should_scrape = True
                            break

                if 'blacklist' in link_policy:
                    for blacklist_item in link_policy['blacklist']:
                        if blacklist_item in download_url:
                            should_scrape = False
                            break

            if should_scrape:
                policy = copy.copy(link_policy)
                # make sure we reduce the depth level by one each time we recurse
                policy['levels'] -= 1
                # no extension is most likely going to return HTML as well.
                is_html = os.path.splitext(download_url)[1] in ['.htm', '.html', '.xhtml', '']
                derived_filename = derive_filename(download_url)
                new_url = derived_filename
                if is_html:
                    if not download_url in downloaded_pages:
                        LOGGER.info("Downloading linked HTML page {}".format(download_url))

                        global archiver
                        if archiver:
                            info = archiver.get_page(download_url, link_policy=policy, run_js=run_js)
                            filename = info['index_path'].replace(archiver.root_dir + os.sep, '')
                        else:
                            info = archive_page(download_url, destination, link_policy=policy, run_js=run_js, relative_links=relative_links)
                            filename = info['index_path'].replace(destination + os.sep, '')

                        new_url = filename
                        downloaded_pages[download_url] = new_url
                        assert info, "Download failed for {}".format(download_url)

                        if resource_urls:
                            resource_urls[download_url] = filename
                    else:
                        new_url = downloaded_pages[download_url]

                    if relative_links and base_url:
                        page_filename = derive_filename(base_url)
                        new_url = get_relative_url_for_archive_filename(new_url, page_filename)
                else:
                    full_path = os.path.join(destination, derived_filename)
                    new_url = derived_filename
                    if not os.path.exists(full_path):
                        LOGGER.info("Downloading file {}".format(url))
                        download_file(url, destination, filename=derived_filename)
                    else:
                        LOGGER.info("File already downloaded, skipping: {}".format(url))

                if node.name == 'iframe':
                    node['src'] = new_url
                elif node.name == 'a':
                    node['href'] = new_url

    # ... and also run the middleware on CSS/JS embedded in the page source to
    # get linked files.
    for node in doc.select('style'):
        node.string = css_content_middleware(node.get_text(), url='')

    for node in doc.select('script'):
        if not node.attrs.get('src'):
            node.string = js_content_middleware(node.get_text(), url='')

    return doc


def get_archive_filename(url, page_url=None, download_root=None, resource_urls=None):
    file_url_parsed = urlparse(url)
    page_url_parsed = None
    page_domain = None
    if page_url:
        page_url_parsed = urlparse(page_url)
        page_domain = page_url_parsed.netloc

    LOGGER.debug(" page_url = {}".format(page_url))

    domain = file_url_parsed.netloc

    if not domain and page_domain:
        domain = page_domain

    assert domain, "Relative links need page_url to be set in order to resolve them."

    rel_path = urlparse(urljoin(page_url, url))

    local_path = url2pathname(rel_path.netloc + rel_path.path)
    _path, ext = os.path.splitext(local_path)

    if file_url_parsed.query:
        # Append the query to the filename, so that the filename is unique for each set of params.
        query_string = "_{}".format(file_url_parsed.query.replace('=', '_').replace('&', '_'))
        local_path = _path + query_string + ext
        LOGGER.debug("local_path is now {}".format(local_path))

    local_dir_name = local_path
    if ext != '':
        local_dir_name = os.path.dirname(local_path)
    LOGGER.debug("local_path = {}, local_dir_name = {}".format(local_path, local_dir_name))

    if local_dir_name != local_path and resource_urls is not None:
        full_dir = os.path.join(download_root, local_dir_name)
        os.makedirs(full_dir, exist_ok=True)

        # TODO: Determine the best way to handle non-resource file links, e.g. links to other pages
        # Right now, this code depends on any file links having an extension, as in this function
        # we don't know the mimetype of the resource yet. We should probably pass in mimetype to this
        # function so we can construct filenames for extensionless URLs.
        if os.path.splitext(local_path)[1].strip() != '':
            LOGGER.debug("replacing {} with {}".format(url, local_path))
            resource_urls[url] = local_path
    return local_path


def get_relative_url_for_archive_filename(filename, relative_to):
    if os.path.isfile(relative_to) or os.path.splitext(relative_to)[1] != '':
        relative_to = os.path.dirname(relative_to)
    return os.path.relpath(filename, relative_to).replace("\\", "/")


def archive_page(url, download_root, link_policy=None, run_js=False, strict=False, relative_links=False):
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
        content, props = asyncio.get_event_loop().run_until_complete(load_page(url, strict=strict))
    else:
        response = make_request(url)
        props = {'cookies': requests.utils.dict_from_cookiejar(response.cookies), 'url': response.url}
        if not 'charset' in response.headers['Content-Type']:
            # It seems requests defaults to ISO-8859-1 when the headers don't explicitly declare an
            # encoding. In this case, we're better off using chardet to guess instead.
            encoding = chardet.detect(response.content)
            if encoding and 'encoding' in encoding:
                response.encoding = encoding['encoding']
            LOGGER.warning("Encoding = {}".format(response.encoding))
        content = response.text

    # url may be redirected, for relative link handling we want the final URL that was loaded.
    url = props['url']

    # get related assets
    parts = urlparse(url)
    if not parts.scheme:
        parts.scheme = 'https'
    base_url = urljoin("{}://{}".format(parts.scheme, parts.netloc), parts.path[:parts.path.rfind('/')])
    resource_urls = {}

    if content:
        LOGGER.warning("Downloading linked files for {}".format(url))
        page_url = url

        def get_resource_filename(url):
            return get_archive_filename(url, page_url, download_root, resource_urls)
        doc = download_static_assets(content, download_root, base_url, derive_filename=get_resource_filename,
                               link_policy=link_policy, run_js=run_js, resource_urls=resource_urls,
                               relative_links=relative_links)

        download_path = os.path.join(download_root, get_archive_filename(url, page_url, download_root))
        _path, ext = os.path.splitext(download_path)
        index_path = download_path
        if '.htm' not in ext:
            if download_path.endswith('/'):
                index_path = download_path + 'index.html'
            else:
                index_path = download_path + '.html'

        index_dir = os.path.dirname(index_path)

        new_content = doc.prettify()
        # Replace any links with relative links that we haven't changed already.
        # TODO: Find a way to determine when this check is no longer needed.
        new_content = replace_links(new_content, resource_urls, download_root, index_dir, relative_links=relative_links)

        os.makedirs(index_dir, exist_ok=True)

        soup = BeautifulSoup(new_content, features='lxml')
        f = open(index_path, 'wb')
        f.write(soup.prettify(encoding="utf-8"))
        f.close()


        page_info = {
            'url': url,
            'cookies': props['cookies'],
            'index_path': index_path,
            'resources': list(resource_urls.values()),
            'resource_urls': resource_urls
        }
        LOGGER.info("archive_page finished...")
        return page_info

    return None


def _is_blacklisted(url, url_blacklist):
    return any((item in url.lower()) for item in url_blacklist)


def download_in_parallel(urls, func=None, max_workers=5):
    """
    Takes a set of URLs, and downloads them in parallel
    :param urls: A list of URLs to download in parallel
    :param func: A function that takes the URL as a parameter.
                 If not specified, defaults to a session-managed
                 requests.get function.
    :return: A dictionary of func return values, indexed by URL
    """
    if func is None:
        func = requests.get

    results = {}
    start = 0
    end = len(urls)
    batch_size = 100
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        while start < end:
            batch = urls[start:end]
            futures = {}
            for url in batch:
                futures[executor.submit(func, url)] = url

            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                    results[url] = result
                except:
                    raise
            start = start + batch_size

    return results


class ArchiveDownloader:
    def __init__(self, root_dir, relative_links=True):
        self.root_dir = root_dir
        self.cache_file = os.path.join(self.root_dir, 'archive_files.json')
        self.cache_data = {}

        # This is temporarily configurable for ArchiveDownloader-based chefs that
        # rely on the old, non-relative behavior of using full archive paths.
        # This can be hardcoded to True once existing chefs have been updated.
        self.relative_links = relative_links

        if os.path.exists(self.cache_file):
            self.cache_data = json.load(open(self.cache_file))

        global archiver
        archiver = self

    def __del__(self):
        global archiver
        archiver = None

    def save_cache_data(self):
        with open(self.cache_file, 'w') as f:
            f.write(json.dumps(self.cache_data, ensure_ascii=False, indent=2))

    def clear_cache_data(self):
        self.cache_data = {}
        self.save_cache_data()

    def get_page(self, url, refresh=False, link_policy=None, run_js=False, strict=False):
        if refresh or not url in self.cache_data:
            self.cache_data[url] = archive_page(url, download_root=self.root_dir, link_policy=link_policy, run_js=run_js, strict=strict, relative_links=self.relative_links)
            self.save_cache_data()

        return self.cache_data[url]

    def get_relative_index_path(self, url):
        if url in self.cache_data and 'index_path' in self.cache_data[url]:
            if not self.relative_links:
                # we copy the main page to index.html in the root of the page archive.
                return "index.html"
            return self.cache_data[url]['index_path'].replace(self.root_dir + os.sep, '')

        return None

    def find_page_by_index_path(self, index_path):
        for url in self.cache_data:
            if self.cache_data[url]['index_path'] == index_path:
                return self.cache_data[url]

        return None

    def get_page_soup(self, url):
        if not url in self.cache_data:
            raise KeyError("Unable to find page {} in archive. Did you call get_page?".format(url))

        info = self.cache_data[url]
        # lxml enables some nice features like being able to search for individual
        # class names using BeautifulSoup, so let's just require it.
        soup = BeautifulSoup(open(info['index_path'], 'rb'), features='lxml')
        return soup

    def create_dependency_zip(self, count_threshold=2):
        resource_counts = {}
        for url in self.cache_data:
            info = self.cache_data[url]
            resources = info['resources']
            for resource in resources.values():
                if not resource in resource_counts:
                    resource_counts[resource] = 0
                resource_counts[resource] += 1

        shared_resources = []
        for res in resource_counts:
            if resource_counts[res] >= count_threshold:
                shared_resources.append(res)

        temp_dir = tempfile.mkdtemp()
        self._copy_resources_to_dir(temp_dir, shared_resources)

        self.dep_path = create_predictable_zip(temp_dir)
        return self.dep_path

    def _copy_resources_to_dir(self, base_dir, resources):
        for res in resources:
            res_path = res
            if res_path.startswith(self.root_dir):
                res_path = res_path.replace(self.root_dir, '')
                if res_path.startswith('/'):
                    res_path = res_path[1:]
            full_path = os.path.join(self.root_dir, res_path)
            dest_path = os.path.join(base_dir, res_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if os.path.isfile(full_path):
                shutil.copy2(full_path, dest_path)

    def create_zip_dir_for_page(self, url):
        if not url in self.cache_data:
            raise KeyError("Please ensure you call get_page before calling this function to download the content.")
        temp_dir = tempfile.mkdtemp()
        info = self.cache_data[url]

        # TODO: Add dependency zip handling that replaces links with the dependency zip location
        self._copy_resources_to_dir(temp_dir, info['resources'])
        for res_url in info['resource_urls']:
            if res_url in self.cache_data:
                resources = self.cache_data[res_url]['resources']
                self._copy_resources_to_dir(temp_dir, resources)

        index_path = self.get_relative_index_path(url)

        shutil.copy(info['index_path'], os.path.join(temp_dir, index_path))
        return temp_dir

    def export_page_as_zip(self, url):
        zip_dir = self.create_zip_dir_for_page(url)
        info = self.cache_data[url]

        entrypoint = None
        if self.relative_links:
            entrypoint = self.get_relative_index_path(url)

        return create_predictable_zip(zip_dir, entrypoint=entrypoint)
