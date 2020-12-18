import unittest

from ricecooker.utils import downloader


class TestArchiver(unittest.TestCase):
    def test_get_archive_filename_absolute(self):
        link = 'https://learningequality.org/kolibri.png'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, download_root='./', urls_to_replace=urls_to_replace)

        assert result == 'learningequality.org/kolibri.png'
        assert urls_to_replace[link] == 'learningequality.org/kolibri.png'

    def test_get_archive_filename_relative(self):
        link = '../kolibri.png'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', urls_to_replace=urls_to_replace)

        assert result == 'learningequality.org/kolibri.png'
        assert urls_to_replace[link] == 'learningequality.org/kolibri.png'
