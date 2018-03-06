import os
import requests
import signal
import time
import urllib

from bs4 import BeautifulSoup
from selenium import webdriver
from urllib.parse import urlparse, unquote

from .caching import FileCache, CacheControlAdapter
from ricecooker.config import PHANTOMJS_PATH



# create a default session with basic caching mechanisms (similar to what a browser would do)
sess = requests.Session()
cache = FileCache('.webcache')
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
