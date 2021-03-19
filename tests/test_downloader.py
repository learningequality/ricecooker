import os
import unittest

from ricecooker.utils import downloader


class TestArchiver(unittest.TestCase):
    def test_get_archive_filename_absolute(self):
        link = 'https://learningequality.org/kolibri.png'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, download_root='./', resource_urls=urls_to_replace)

        expected = os.path.join('learningequality.org', 'kolibri.png')

        assert result == expected
        assert urls_to_replace[link] == expected

    def test_get_archive_filename_relative(self):
        link = '../kolibri.png'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', resource_urls=urls_to_replace)

        expected = os.path.join('learningequality.org', 'kolibri.png')

        assert result == expected
        assert urls_to_replace[link] == expected

    def test_get_archive_filename_with_query(self):
        link = '../kolibri.png?1.2.3'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', resource_urls=urls_to_replace)

        expected = os.path.join('learningequality.org', 'kolibri_1.2.3.png')

        assert result == expected
        assert urls_to_replace[link] == expected

        link = '../kolibri.png?v=1.2.3&i=u'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', resource_urls=urls_to_replace)

        expected = os.path.join('learningequality.org', 'kolibri_v_1.2.3_i_u.png')

        assert result == expected
        assert urls_to_replace[link] == expected

    def test_archive_path_as_relative_url(self):
        link = '../kolibri.png?1.2.3'
        page_link = 'https://learningequality.org/team/index.html'
        page_filename = downloader.get_archive_filename(page_link, download_root='./')
        link_filename = downloader.get_archive_filename(link, page_url=page_link, download_root='./')
        rel_path = downloader.get_relative_url_for_archive_filename(link_filename, page_filename)
        assert rel_path == '../kolibri_1.2.3.png'
