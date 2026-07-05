import mimetypes
import os
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse

import responses

from ricecooker.utils import downloader

TESTCONTENT = Path(__file__).resolve().parent / "testcontent"

# Portless host used to serve the checked-in sample tree. A real host (no
# ":port") keeps the archived paths free of colons, which are illegal in
# Windows filenames - the reason the previous embedded-server version of this
# test failed on Windows.
SAMPLE_HOST = "https://example.org"


def _serve_sample_tree(request):
    """responses callback: serve files from tests/testcontent as a static site.

    Maps the request URL path onto the on-disk sample tree so the fixtures
    checked in for this test are served verbatim, no local web server needed.
    """
    rel_path = unquote(urlparse(request.url).path).lstrip("/")
    file_path = TESTCONTENT / rel_path
    if not file_path.is_file():
        return (404, {}, b"")
    ext = file_path.suffix
    if ext == ".html":
        content_type = "text/html; charset=utf-8"
    elif ext == "":
        # Extensionless resources in this fixture are stylesheets; Google Fonts
        # serves its CSS from an extensionless URL, which is what this test
        # exercises.
        content_type = "text/css"
    else:
        content_type = (
            mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        )
    return (200, {"Content-Type": content_type}, file_path.read_bytes())


class TestArchiver(unittest.TestCase):
    def test_get_archive_filename_absolute(self):
        link = "https://learningequality.org/kolibri.png"

        urls_to_replace = {}
        result = downloader.get_archive_filename(
            link, download_root="./", resource_urls=urls_to_replace
        )

        expected = os.path.join("learningequality.org", "kolibri.png")

        assert result == expected
        assert urls_to_replace[link] == expected

    def test_get_archive_filename_relative(self):
        link = "../kolibri.png"
        page_link = "https://learningequality.org/team/index.html"

        urls_to_replace = {}
        result = downloader.get_archive_filename(
            link, page_url=page_link, download_root="./", resource_urls=urls_to_replace
        )

        expected = os.path.join("learningequality.org", "kolibri.png")

        assert result == expected
        assert urls_to_replace[link] == expected

    def test_get_archive_filename_with_query(self):
        link = "../kolibri.png?1.2.3"
        page_link = "https://learningequality.org/team/index.html"

        urls_to_replace = {}
        result = downloader.get_archive_filename(
            link, page_url=page_link, download_root="./", resource_urls=urls_to_replace
        )

        expected = os.path.join("learningequality.org", "kolibri_1.2.3.png")

        assert result == expected
        assert urls_to_replace[link] == expected

        link = "../kolibri.png?v=1.2.3&i=u"
        page_link = "https://learningequality.org/team/index.html"

        urls_to_replace = {}
        result = downloader.get_archive_filename(
            link, page_url=page_link, download_root="./", resource_urls=urls_to_replace
        )

        expected = os.path.join("learningequality.org", "kolibri_v_1.2.3_i_u.png")

        assert result == expected
        assert urls_to_replace[link] == expected

    def test_archive_path_as_relative_url(self):
        link = "../kolibri.png?1.2.3"
        page_link = "https://learningequality.org/team/index.html"
        page_filename = downloader.get_archive_filename(page_link, download_root="./")
        link_filename = downloader.get_archive_filename(
            link, page_url=page_link, download_root="./"
        )
        rel_path = downloader.get_relative_url_for_archive_filename(
            link_filename, page_filename
        )
        assert rel_path == "../kolibri_1.2.3.png"


# The sample tree lives under a subject folder mirroring a real PreTeXt book:
# activecalculus.org (the page) references a stylesheet from fonts.googleapis.com
# via an extensionless URL, whose CSS in turn references a font on
# fonts.gstatic.com.
SAMPLE_ROOT = "samples/PreTeXt_book_test_manually_cleaned_urls"
# The Google Fonts stylesheet URL is extensionless; the original had a colon,
# replaced with an underscore so the fixture file checks out on Windows.
CSS_URL_PART = "css2_family_Material+Symbols+Outlined_opsz,wght,FILL,GRAD@24,400,0,0"


@responses.activate
def test_pretextbook_css_fetch():
    """A stylesheet linked via an extensionless URL is archived and rewritten.

    Regression test for two bugs when archiving a PreTeXt book: the CSS
    ``<link>`` (matched by ``rel="stylesheet"``, not a ``.css`` extension) was
    skipped, and the generated ``index.css`` for the extensionless resource was
    dumped at the archive root instead of nested under the resource's own path,
    which made its relative font references escape the archive directory.
    """
    responses.add_callback(
        responses.GET,
        re.compile(re.escape(SAMPLE_HOST) + r"/.*"),
        callback=_serve_sample_tree,
    )

    page_url = "{}/{}/activecalculus.org/single2e/sec-5-2-FTC2.html".format(
        SAMPLE_HOST, SAMPLE_ROOT
    )

    with tempfile.TemporaryDirectory() as download_root:
        archive = downloader.ArchiveDownloader(download_root)
        archive.get_page(page_url)

        book_dest_dir = Path(download_root) / "example.org" / SAMPLE_ROOT

        # The page's stylesheet link is rewritten to the nested index.css.
        page_html = (
            book_dest_dir / "activecalculus.org" / "single2e" / "sec-5-2-FTC2.html"
        ).read_text()
        assert "../../fonts.googleapis.com/" + CSS_URL_PART + "/index.css" in page_html

        # The extensionless stylesheet is nested under its own path as index.css,
        # not clobbered at the archive root.
        index_css = book_dest_dir / "fonts.googleapis.com" / CSS_URL_PART / "index.css"
        css_contents = index_css.read_text()
        assert "fonts.gstatic.com/s/materialsymbolsoutlined" in css_contents

        # The font referenced from the CSS is downloaded to its own nested path.
        font_path = (
            book_dest_dir
            / "fonts.gstatic.com"
            / "s"
            / "materialsymbolsoutlined"
            / "v290"
            / "material_symbols.woff"
        )
        assert font_path.stat().st_size > 0
