#!/usr/bin/env python
from bs4 import BeautifulSoup
import requests
import tempfile

from ricecooker.chefs import SushiChef
from ricecooker.classes import licenses
from ricecooker.classes.files import HTMLZipFile, SubtitleFile, VideoFile
from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip


# CHANNEL SETTINGS
SOURCE_DOMAIN = "<yourdomain.org>"  #
SOURCE_ID = "<yourid>"              # an alphanumeric ID referring to this channel
CHANNEL_TITLE = "<channeltitle>"    # a human-readable title
CHANNEL_LANGUAGE = "en"             # language of channel


sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)


def make_fully_qualified_url(url):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://en.wikipedia.org" + url
    assert url.startswith("http"), "Bad URL (relative to unknown location): " + url
    return url


def make_request(url, *args, **kwargs):
    response = sess.get(url, *args, **kwargs)
    if response.status_code != 200:
        print("NOT FOUND:", url)
    elif not response.from_cache:
        print("NOT CACHED:", url)
    return response


def get_parsed_html_from_url(url, *args, **kwargs):
    html = make_request(url, *args, **kwargs).content
    return BeautifulSoup(html, "html.parser")


class WikipediaVideoChef(SushiChef):
    """
    Creates a sample Kolibri channel with a video node and subs in two languages.
    """

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
        videos_topic = TopicNode(source_id="/wiki/Category:Articles_containing_video_clips",
                                 title="Articles containing video clips")
        channel.add_child(videos_topic)

        thumbnail_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/A_Is_for_Atom_1953.webm/220px--A_Is_for_Atom_1953.webm.jpg'
        page = download_wikipedia_page('/wiki/Category:Articles_containing_video_clips',
                                       thumbnail_url, 'A Is for Atom')
        videos_topic.add_child(page)

        video_url = 'https://upload.wikimedia.org/wikipedia/commons/e/ee/A_Is_for_Atom_1953.webm'
        video_file = VideoFile(path=video_url)
        video_node = VideoNode(title='A Is for Atom 1953', source_id='A_Is_for_Atom_1953.webm',
                               files=[video_file], license=licenses.PublicDomainLicense())

        subtitle_url = 'https://commons.wikimedia.org/w/api.php?action=timedtext&title=File%3AA_Is_for_Atom_1953.webm&lang={}&trackformat=srt'
        subtitle_languages = [
            'en',
            'es',
        ]
        for lang in subtitle_languages:
            subtitle_file = SubtitleFile(path=subtitle_url.format(lang), language=lang, subtitlesformat='srt')
            video_node.add_file(subtitle_file)

        videos_topic.add_child(video_node)

        return channel


def download_wikipedia_page(url, thumbnail, title):

    # create a temp directory to house our downloaded files
    dest_path = tempfile.mkdtemp()

    # download the main wikipedia page, apply a middleware processor, and call it index.html
    local_ref, _ = download_file(
        make_fully_qualified_url(url),
        dest_path,
        filename="index.html",
        middleware_callbacks=process_wikipedia_page,
        request_fn=make_request,
    )

    # turn the temp folder into a zip file
    zip_path = create_predictable_zip(dest_path)

    # create an HTML5 app node
    html5app = HTML5AppNode(
        files=[HTMLZipFile(zip_path)],
        title=title,
        thumbnail=thumbnail,
        source_id=url.split("/")[-1],
        license=licenses.PublicDomainLicense(),
    )

    return html5app


def process_wikipedia_page(content, baseurl, destpath, **kwargs):

    page = BeautifulSoup(content, "html.parser")

    for image in page.find_all("img"):
        rel_path, _ = download_file(make_fully_qualified_url(image["src"]), destpath,
                                    request_fn=make_request)
        image["src"] = rel_path

    return str(page)


if __name__ == '__main__':
    """
    Call this script using:
        ./wikipedia_video_chef.py --token=<t>
    """
    wikichef = WikipediaVideoChef()
    wikichef.main()


# Run the chef using
#   ./wikipedia_video_chef.py  --thumbnails --token=<yourstudiotoken>
# and you should see something like:
#
#    Downloading https://commons.wikimedia.org/w/api.php?action=timedtext&title=File%3AA_Is_for_Atom_1953.webm&lang=en&trackformat=srt
#    --- Downloaded 196d262476187581c3253c126cfdd394.vtt
#    Downloading https://commons.wikimedia.org/w/api.php?action=timedtext&title=File%3AA_Is_for_Atom_1953.webm&lang=es&trackformat=srt
#    --- Downloaded 014ae576fc74b7fb9d0da0b0a747f9d7.vtt
#
# which indicates the two .srt files were successfully downloaded form the
# weird-looking URLs and automatically converted to VTT format.
