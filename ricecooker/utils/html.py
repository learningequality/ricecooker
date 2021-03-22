import logging
import os
import re
import requests
import signal
import time
import urllib

import chardet

from bs4 import BeautifulSoup
from selenium import webdriver
from urllib.parse import urlparse, unquote
from urllib.request import pathname2url

from .caching import FileCache, CacheControlAdapter
from ricecooker.config import LOGGER, PHANTOMJS_PATH, STRICT



# create a default session with basic caching mechanisms (similar to what a browser would do)
sess = requests.Session()
cache = FileCache('.webcache', use_dir_lock=True)
basic_adapter = CacheControlAdapter(cache=cache)
sess.mount('http://', basic_adapter)
sess.mount('https://', basic_adapter)

if PHANTOMJS_PATH is None:
    PHANTOMJS_PATH = os.path.join(os.getcwd(), "node_modules", "phantomjs-prebuilt", "bin", "phantomjs")


class WebDriver(object):

    def __init__(self, url, delay=1000):
        self.url = url
        self.delay = delay

    def __enter__(self):
        if not os.path.isfile(PHANTOMJS_PATH):
            raise Exception("You must install phantomjs-prebuilt in the directory"
                            " you're running in with `npm install phantomjs-prebuilt`"
                            " or set the environment variable `PHANTOMJS_PATH`")
        self.driver = webdriver.PhantomJS(executable_path=PHANTOMJS_PATH)
        self.driver.get(self.url)
        time.sleep(self.delay / 1000.0)
        return self.driver

    def __exit__(self ,type, value, traceback):
        # driver.quit() by itself doesn't suffice to fully terminate spawned
        # PhantomJS processes:
        # see https://github.com/seleniumhq/selenium/issues/767
        self.driver.service.process.send_signal(signal.SIGTERM)
        self.driver.quit()


def get_generated_html_from_driver(driver, tagname="html"):
    driver.execute_script("return document.getElementsByTagName('{tagname}')[0].innerHTML".format(tagname=tagname))


def replace_links(content, urls_to_replace, download_root=None, content_dir=None, relative_links=False):
    for key in urls_to_replace:
        value = urls_to_replace[key]
        if key == value:
            continue
        url_parts = urlparse(key)

        rel_path = None
        # Because of how derive_filename works, all relative URLs are converted to absolute.
        # So here we reconstruct the relative URL so we can replace relative links in the source.
        if download_root and content_dir:
            rel_path = os.path.relpath(os.path.join(download_root, value), content_dir)

        # Make sure we remove any native path separators in constructed paths
        value = pathname2url(value)
        if rel_path:
            rel_path = pathname2url(rel_path)

        if relative_links:
            value = pathname2url(os.path.relpath(os.path.join(download_root, value), content_dir))

        # When we get an absolute URL, it may appear in one of three different ways in the page:
        key_variants = [
            # 1. /path/to/file.html
            key.replace(url_parts.scheme + '://' + url_parts.netloc, ''),
            # 2. https://www.domain.com/path/to/file.html
            key,
            # 3. //www.domain.com/path/to/file.html
            key.replace(url_parts.scheme + ':', ''),
        ]

        if rel_path and content_dir:
            # We also add relative paths from the index (see note above).
            key_variants.append(rel_path)

        orig_content = content

        # The simple replace rules above won't work with srcset links, as they can be multiple urls that are
        # comma-separated and may contain resolution specifiers like a specific width or 1x/2x values.
        # Here we use a simple regex to grab srcset and parse and rebuild the value.
        srcset_re = "(srcset=['\"])(.+)([\"'])"
        srcset_links = re.findall(srcset_re, content, flags=re.I | re.M)
        for variant in key_variants:
            if variant == value:
                continue
            # searching within quotes ensures we only replace the exact URL we are
            # trying to replace
            # we avoid using BeautifulSoup because Python HTML parsers can be destructive and
            # do things like strip out the doctype.
            content = content.replace('="{}"'.format(variant), '="{}"'.format(value))
            content = content.replace('url({})'.format(variant), 'url({})'.format(value))

            for match in srcset_links:
                url = match[1]
                new_url_parts = []
                for src in url.split(","):
                    parts = src.split(" ")
                    new_parts = []
                    for part in parts:
                        if part.strip() == variant:
                            # this preserves whitespace
                            part = part.replace(variant, value)
                        new_parts.append(part)
                    new_url_parts.append(" ".join(new_parts))
                new_url = ",".join(new_url_parts)
                new_string = "".join(match).replace(url, new_url)
                content = content.replace("".join(match), new_string)

        if content == orig_content:
            LOGGER.debug("link not replaced: {}".format(key))
            LOGGER.debug("key_variants = {}".format(key_variants))

    return content


def calculate_relative_url(url, filename=None, baseurl=None, subpath=None):
    """
    Calculate the relative path for a URL relative to a base URL, possibly also injecting in a subpath prefix.
    """

    # ensure the provided subpath is a list
    if isinstance(subpath, str):
        subpath = subpath.strip("/").split("/")
    elif subpath is None:
        subpath = []

    # if a base path was supplied, calculate the file's subpath relative to it
    if baseurl:
        baseurl = urllib.parse.urljoin(baseurl, ".")  # ensure baseurl is normalized (to remove '/./' and '/../')
        assert url.startswith(baseurl), "URL {} must start with baseurl {}".format(url, baseurl)
        subpath = subpath + url[len(baseurl):].strip("/").split("/")[:-1]

    # if we don't have a filename, extract it from the URL
    if not filename:
        filename = unquote(urlparse(url).path.split("/")[-1])

    # calculate the url path to use to refer to this file, relative to destpath
    relative_file_url = "/".join(["."] + subpath + [filename])

    return relative_file_url, subpath, filename


def download_file(url, destpath, filename=None, baseurl=None, subpath=None, middleware_callbacks=None, middleware_kwargs=None, request_fn=sess.get):
    """
    Download a file from a URL, into a destination folder, with optional use of relative paths and middleware processors.

    - If `filename` is set, that will be used as the name of the file when it's written to the destpath.
    - If `baseurl` is specified, the file will be put into subdirectory of destpath per the url's path relative to the baseurl.
    - If `subpath` is specified, it will be appended to destpath before deciding where to write the file.
    - If `middleware_callbacks` is specified, the returned content will be passed through those function(s) before being returned.
        - If `middleware_kwargs` are also specified, they will also be passed in to each function in middleware_callbacks.
    """

    relative_file_url, subpath, filename = calculate_relative_url(url, filename=filename, baseurl=baseurl, subpath=subpath)

    LOGGER.info("Download called for {}".format(url))
    # ensure that the destination directory exists
    fulldestpath = os.path.join(destpath, *subpath)
    os.makedirs(fulldestpath, exist_ok=True)

    # make the actual request to the URL
    response = request_fn(url)
    content = response.content

    if STRICT:
        response.raise_for_status()
    elif response.status_code >= 400:
        LOGGER.warning("URL {} returned status {}".format(url, response.status_code))

    # if there are any middleware callbacks, apply them to the content
    if middleware_callbacks:
        if 'content-type' in response.headers:
            type = response.headers['content-type'].split(';')[0]
            # Rely on requests to convert bytes to unicode for us when it's a text file
            # otherwise, we just use bytes
            if type.startswith('text'):
                # It seems requests defaults to ISO-8859-1 when the headers don't explicitly declare an
                # encoding. In this case, we're better off using chardet to guess instead.
                encoding = chardet.detect(response.content)
                if encoding and 'encoding' in encoding:
                    response.encoding = encoding['encoding']
                LOGGER.warning("encoding for {} = {}".format(url, response.encoding))
                content = response.text

        if not isinstance(middleware_callbacks, list):
            middleware_callbacks = [middleware_callbacks]
        kwargs = {
            "url": url,
            "destpath": destpath,
            "filename": filename,
            "baseurl": baseurl,
            "subpath": subpath,
            "fulldestpath": fulldestpath,
            "response": response,
        }
        kwargs.update(middleware_kwargs or {})
        for callback in middleware_callbacks:
            content = callback(content, **kwargs)

    # ensure content is encoded, as we're doing a binary write
    if isinstance(content, str):
        content = content.encode('utf-8')

    # calculate the final destination for the file, and write the content out to there
    dest = os.path.join(fulldestpath, filename)
    with open(dest, "wb") as f:
        f.write(content)

    return relative_file_url, response
