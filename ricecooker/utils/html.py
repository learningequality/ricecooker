import os
import requests
import time
import urllib

from bs4 import BeautifulSoup
from css_html_js_minify.minify import process_multiple_files, walk2list, Pool, cpu_count, partial
from selenium import webdriver
from urllib.parse import urlparse, unquote

from .caching import FileCache, CacheControlAdapter


# create a default session with basic caching mechanisms (similar to what a browser would do)
sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
sess.mount('http://', basic_adapter)
sess.mount('https://', basic_adapter)

PHANTOMJS_PATH = os.path.join(os.getcwd(), "node_modules", "phantomjs-prebuilt", "bin", "phantomjs")


class WebDriver(object):

    def __init__(self, url, delay=1000):
        self.url = url
        self.delay = delay

    def __enter__(self):
        # self.driver = webdriver.Firefox()
        if not os.path.isfile(PHANTOMJS_PATH):
            raise Exception("You must first install phantomjs-prebuilt in the directory you're running from, with `npm install phantomjs-prebuilt`")

        self.driver = webdriver.PhantomJS(executable_path=PHANTOMJS_PATH)
        self.driver.get(self.url)
        time.sleep(self.delay / 1000.0)
        return self.driver

    def __exit__(self ,type, value, traceback):
        self.driver.close()


def get_generated_html_from_driver(driver, tagname="html"):
    driver.execute_script("return document.getElementsByTagName('{tagname}')[0].innerHTML".format(tagname=tagname))


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
        assert url.startswith(baseurl), "URL must start with baseurl"
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

    # ensure that the destination directory exists
    fulldestpath = os.path.join(destpath, *subpath)
    os.makedirs(fulldestpath, exist_ok=True)

    # make the actual request to the URL
    response = request_fn(url)
    content = response.content

    # if there are any middleware callbacks, apply them to the content
    if middleware_callbacks:
        content = content.decode()
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
        content = content.encode()

    # calculate the final destination for the file, and write the content out to there
    dest = os.path.join(fulldestpath, filename)
    with open(dest, "wb") as f:
        f.write(content)

    return relative_file_url, response

import logging

def minimize_html_css_js(directory, blacklist=None):

    original_log_level = logging.getLogger().getLevel()
    logging.getLogger().setLevel(logging.ERROR)

    blacklist = tuple(blacklist or []) + (".min.css", ".min.js")

    list_of_files = walk2list(directory, (".css", ".js", ".html"), blacklist)

    pool = Pool(cpu_count())  # Multiprocessing Async
    pool.map_async(partial(
            process_multiple_files, watch=False,
            wrap=False, timestamp=False,
            comments=False, sort=True,
            overwrite=True, zipy=False,
            prefix="", add_hash=False),
        list_of_files)
    pool.close()
    pool.join()

    logging.getLogger().setLevel(original_log_level)
