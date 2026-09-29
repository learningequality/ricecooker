#!/usr/bin/env python
from bs4 import BeautifulSoup
from le_utils.constants import licenses

from ricecooker import config
from ricecooker.chefs import SushiChef
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.config import LOGGER


def make_fully_qualified_url(url):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://en.wikipedia.org" + url
    if not url.startswith("http"):
        LOGGER.warning("Skipping bad URL (relative to unknown location): " + url)
        return None
    return url


class WikipediaChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Wikipedia fruit and vegetables",
        "CHANNEL_SOURCE_DOMAIN": "<yourdomain.org>",  # where content comes from
        "CHANNEL_SOURCE_ID": "<unique id for the channel>",  # CHANGE ME!!!
        "CHANNEL_LANGUAGE": "en",
        "CHANNEL_THUMBNAIL": "https://lh3.googleusercontent.com/zwwddqxgFlP14DlucvBV52RUMA-cV3vRvmjf-iWqxuVhYVmB-l8XN9NDirb0687DSw=w300",
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        for page, title in (
            ("List_of_citrus_fruits", "Citrus!"),
            ("List_of_potato_cultivars", "Potatoes!"),
        ):
            topic = TopicNode(source_id=page, title=title)
            channel.add_child(topic)
            add_subpages_from_wikipedia_list(
                topic, "https://en.wikipedia.org/wiki/" + page
            )
        return channel


def add_subpages_from_wikipedia_list(topic, list_url):

    # to understand how the following parsing works, look at:
    #   1. the source of the page (e.g. https://en.wikipedia.org/wiki/List_of_citrus_fruits), or inspect in chrome dev tools
    #   2. the documentation for BeautifulSoup version 4: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

    # the session ricecooker downloads with, so DOMAIN_AUTH_HEADERS and its User-Agent apply
    response = config.DOWNLOAD_SESSION.get(list_url)
    response.raise_for_status()
    page = BeautifulSoup(response.content, "html.parser")

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

        # extract the URL for the subpage
        url = make_fully_qualified_url(link["href"])
        if url is None:
            continue  # skip internal links and or bad URLs

        # attempt to extract a thumbnail for the subpage, from the second column in the table
        image = columns[1].find("img")
        thumbnail_url = make_fully_qualified_url(image["src"]) if image else None
        if thumbnail_url and not (
            thumbnail_url.endswith("jpg") or thumbnail_url.endswith("png")
        ):
            thumbnail_url = None

        # ricecooker archives the page and its images into an HTML5 zip
        topic.add_child(
            ContentNode(
                source_id=url.split("/")[-1],
                title=link.text,
                license=get_license(
                    licenses.CC_BY_SA, copyright_holder="Wikipedia contributors"
                ),
                language="en",
                thumbnail=thumbnail_url,
                uri=url,
            )
        )


if __name__ == "__main__":
    """
    Call this script using:
        ./sushichef.py --token=YOURSTUDIOTOKENHERE9139139f3a23232
    """
    wikichef = WikipediaChef()
    wikichef.main()
