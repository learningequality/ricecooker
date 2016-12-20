import os
import requests
import time

from bs4 import BeautifulSoup

from selenium import webdriver

PHANTOMJS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "node_modules", "phantomjs-prebuilt", "bin", "phantomjs")

try:
    from urlparse import urlparse as parse_url
except ImportError:
    from urllib.parse import urlparse as parse_url

class WebDriver(object):

    def __init__(self, url, delay=1000):
        self.url = url
        self.delay = delay

    def __enter__(self):
        # self.driver = webdriver.Firefox()
        self.driver = webdriver.PhantomJS(executable_path=PHANTOMJS_PATH)
        self.driver.get(self.url)
        time.sleep(self.delay / 1000.0)
        return self.driver

    def __exit__(self ,type, value, traceback):
        self.driver.close()


def get_generated_html_from_driver(driver, tagname="html"):
    driver.execute_script("return document.getElementsByTagName('{tagname}')[0].innerHTML".format(tagname=tagname))

def get_parsed_html_from_url(url):
    html = requests.get(url).content
    return BeautifulSoup(html, "html.parser")

