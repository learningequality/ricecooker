#!/usr/bin/env python
from bs4 import BeautifulSoup
import requests
import tempfile

from ricecooker.chefs import SushiChef
from ricecooker.classes import licenses
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.config import LOGGER


# CHANNEL SETTINGS
SOURCE_DOMAIN = "<yourdomain.org>" #
SOURCE_ID = "<yourid>"             # an alphanumeric ID refering to this channel
CHANNEL_TITLE = "<channeltitle>"   # a humand-readbale title
CHANNEL_LANGUAGE = "en"            # language of channel


sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)

def make_fully_qualified_url(url):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://en.wikipedia.org" + url
    if not url.startswith("http"):
        LOGGER.warning("Skipping bad URL (relative to unknown location): " + url)
        return None
    return url

def make_request(url, *args, **kwargs):
    response = sess.get(url, *args, **kwargs)
    if response.status_code != 200:
        LOGGER.warning("URL NOT FOUND: " + url)
    elif not response.from_cache:
        LOGGER.warning("NOT CACHED: " + url)
    return response

def get_parsed_html_from_url(url, *args, **kwargs):
    html = make_request(url, *args, **kwargs).content
    return BeautifulSoup(html, "html.parser")



class WikipediaChef(SushiChef):

    def get_channel(self, *args, **kwargs):

        channel = ChannelNode(
            source_domain=SOURCE_DOMAIN,
            source_id=SOURCE_ID,
            title=CHANNEL_TITLE,
            thumbnail="https://lh3.googleusercontent.com/zwwddqxgFlP14DlucvBV52RUMA-cV3vRvmjf-iWqxuVhYVmB-l8XN9NDirb0687DSw=w300",
            language=CHANNEL_LANGUAGE,
        )

        return channel

    def construct_channel(self, *args, **kwargs):

        channel = self.get_channel(**kwargs)
        citrus_topic = TopicNode(source_id="List_of_citrus_fruits", title="Citrus!")
        channel.add_child(citrus_topic)
        add_subpages_from_wikipedia_list(citrus_topic, "https://en.wikipedia.org/wiki/List_of_citrus_fruits")

        potato_topic = TopicNode(source_id="List_of_potato_cultivars", title="Potatoes!")
        channel.add_child(potato_topic)
        add_subpages_from_wikipedia_list(potato_topic, "https://en.wikipedia.org/wiki/List_of_potato_cultivars")

        return channel



def add_subpages_from_wikipedia_list(topic, list_url):

    # to understand how the following parsing works, look at:
    #   1. the source of the page (e.g. https://en.wikipedia.org/wiki/List_of_citrus_fruits), or inspect in chrome dev tools
    #   2. the documentation for BeautifulSoup version 4: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

    # parse the the page into BeautifulSoup format, so we can loop through and manipulate it
    page = get_parsed_html_from_url(list_url)

    # extract the main table from the page
    table = page.find("table")

    # loop through all the rows in the table
    for row in table.find_all("tr"):

        # extract the columns (cells, really) within the current row
        columns = row.find_all("td")

        # some rows are empty, so just skip
        if not columns:
            continue

        # get the link to the subpage
        link = columns[0].find("a")

        # some rows don't have links, so skip
        if not link:
            continue

        # extract the URL and title for the subpage
        url = make_fully_qualified_url(link["href"])
        if url is None:
            continue  # skip internal links and or bad URLs
        title = link.text

        # attempt to extract a thumbnail for the subpage, from the second column in the table
        image = columns[1].find("img")
        thumbnail_url = make_fully_qualified_url(image["src"]) if image else None
        if thumbnail_url and not (thumbnail_url.endswith("jpg") or thumbnail_url.endswith("png")):
            thumbnail_url = None

        # download the wikipedia page into an HTML5 app node
        html5app = download_wikipedia_page(url, thumbnail=thumbnail_url, title=title)

        # add the downloaded HTML5 app node into the topic
        topic.add_child(html5app)


def download_wikipedia_page(url, thumbnail, title):

    # create a temp directory to house our downloaded files
    destpath = tempfile.mkdtemp()

    # downlod the main wikipedia page, apply a middleware processor, and call it index.html
    localref, _ = download_file(
        url,
        destpath,
        filename="index.html",
        middleware_callbacks=process_wikipedia_page,
        request_fn=make_request,
    )

    # turn the temp folder into a zip file
    zippath = create_predictable_zip(destpath)

    # create an HTML5 app node
    html5app = HTML5AppNode(
        files=[HTMLZipFile(zippath)],
        title=title,
        thumbnail=thumbnail,
        source_id=url.split("/")[-1],
        license=licenses.PublicDomainLicense(),
    )

    return html5app


def process_wikipedia_page(content, baseurl, destpath, **kwargs):

    page = BeautifulSoup(content, "html.parser")

    for image in page.find_all("img"):
        relpath, _ = download_file(make_fully_qualified_url(image["src"]), destpath, request_fn=make_request)
        image["src"] = relpath

    return str(page)



if __name__ == '__main__':
    """
    Call this script using:
        ./sushichef.py --token=YOURSTUDIOTOKENHERE9139139f3a23232
    """
    wikichef = WikipediaChef()
    wikichef.main()
