import http.server
import os
import shutil
import unittest
from datetime import datetime
from pathlib import Path
from threading import Thread

import pytest

from ricecooker.utils import downloader

PORT = 8181


@pytest.fixture(scope="module")
def http_local_server():
    # Get the directory containing the current file
    current_file_directory = Path(__file__).resolve().parent
    print(f"Directory of the current file: {current_file_directory}")

    test_content_path = str(current_file_directory / "testcontent")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=test_content_path, **kwargs)

    def spawn_http_server(arg):
        with http.server.HTTPServer(("", PORT), Handler) as httpd:
            # this is a behavior to treat extensionless files as CSS is used by
            # the test test_pretextbook_css_fetch below, see the docs on that test
            # method for more info
            Handler.extensions_map = {"": "text/css"}
            print("serving at port", PORT)
            try:
                httpd.serve_forever()
            except Exception:
                httpd.server_close()

    server_spawning_thread = Thread(target=spawn_http_server, args=(10,))
    server_spawning_thread.daemon = True
    server_spawning_thread.start()
    return server_spawning_thread


# if any changes are needed in the files served out of the "samples" folder, you need to delete the .webcache folder
# that is generated at the project root for the tests to be rerun
@pytest.mark.usefixtures("http_local_server")
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

    # If any changes are needed in the files served out of the "samples" folder, you need to delete the .webcache folder
    # that is generated at the project root for the tests to be rerun
    #
    # This test relies on behavior in the embedded http server declared above as a class level fixture
    # to treat any extensionless file as having a mime type of text/css.
    # Handler.extensions_map = {'': 'text/css'}
    # if another test needs different behavior this may need to be customized or have the fixture be scoped to this test
    # but for now it seems useful to share the resource between this and other future tests.
    def test_pretextbook_css_fetch(self):
        root_page_folder = "PreTeXt_book_test_manually_cleaned_urls"
        # original URL from google has a colon in it, replaced with underscore so that
        # the corresponding folder checked in to the testcontent folder can be safely checked out on Windows
        css_url_part = (
            "css2_family_Material+Symbols+Outlined_opsz,wght,FILL,GRAD@24,400,0,0"
        )

        sushi_url = (
            "http://localhost:"
            + str(PORT)
            + "/samples/"
            + root_page_folder
            + "/activecalculus.org/single2e/sec-5-2-FTC2.html"
        )
        dest_dir = (
            "active_calc_2e_again_"
            + root_page_folder
            + datetime.now().strftime("%Y-%m-%d__%H_%M_%S")
        )
        current_file_dir = Path(__file__).resolve().parent
        downloads_dir = current_file_dir.parent / "downloads"
        try:
            archive = downloader.ArchiveDownloader("downloads/" + dest_dir)
            archive.get_page(sushi_url)

            book_dest_dir = (
                downloads_dir
                / dest_dir
                / "localhost:8181"
                / "samples"
                / root_page_folder
            )
            with open(
                book_dest_dir / "activecalculus.org" / "single2e" / "sec-5-2-FTC2.html",
                "r",
            ) as file:
                page_html = file.read()
                assert (
                    'link href="../../fonts.googleapis.com/'
                    + css_url_part
                    + "/index.css"
                    in page_html
                )

            with open(
                book_dest_dir / "fonts.googleapis.com" / css_url_part / "index.css",
                "r",
            ) as file:
                css_file_contents = file.read()
                # this has an extra '..' compared to what is in the original extensionless css file, because in the course of generating an index.css
                # file to have clear extensions in the archived version the file ends up nested down another level
                assert (
                    'src: url("../../fonts.gstatic.com/s/materialsymbolsoutlined'
                    in css_file_contents
                )

            font_size = os.path.getsize(
                book_dest_dir
                / "fonts.gstatic.com"
                / "s"
                / "materialsymbolsoutlined"
                / "v290"
                / "material_symbols.woff"
            )
            assert font_size > 0
        finally:
            shutil.rmtree(downloads_dir / dest_dir)
