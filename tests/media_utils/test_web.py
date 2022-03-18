import os

from ricecooker.utils import web

test_dir = os.path.dirname(__file__)


def test_get_links():
    filename = os.path.abspath(os.path.join(test_dir, "files", "page_with_links.html"))
    parser = web.HTMLParser(filename)
    links = parser.get_links()

    expected_links = [
        "assets/css/empty.css",
        "assets/css/empty2.css",
        "assets/js/empty.js",
        "assets/images/4933759886_098e9acf93_m.jpg",
        "the_spanish_inquisition.html",
        "http://www.learningequality.org",
        "Wilhelm_Scream.mp3",
    ]

    # make sure the link order is the same to do an equality test
    links.sort()
    expected_links.sort()

    assert links == expected_links


def test_get_local_files():
    filename = os.path.abspath(os.path.join(test_dir, "files", "page_with_links.html"))
    parser = web.HTMLParser(filename)
    links = parser.get_local_files()

    expected_links = [
        "assets/css/empty.css",
        "assets/css/empty2.css",
        "assets/js/empty.js",
        "assets/images/4933759886_098e9acf93_m.jpg",
        "the_spanish_inquisition.html",
        "Wilhelm_Scream.mp3",
    ]

    # make sure the link order is the same to do an equality test
    links.sort()
    expected_links.sort()

    assert links == expected_links


def test_replace_links():
    filename = os.path.abspath(os.path.join(test_dir, "files", "page_with_links.html"))
    parser = web.HTMLParser(filename)

    original_links = [
        "assets/css/empty.css",
        "assets/css/empty2.css",
        "assets/js/empty.js",
        "assets/images/4933759886_098e9acf93_m.jpg",
        "the_spanish_inquisition.html",
        "Wilhelm_Scream.mp3",
    ]

    replacement_links = {}
    for link in original_links:
        replacement_links[link] = "/zipcontent/012343545454645454/{}".format(link)

    new_html = parser.replace_links(replacement_links)

    new_parser = web.HTMLParser(html=new_html)
    links = new_parser.get_links()

    for link in links:
        assert link == replacement_links[link]
