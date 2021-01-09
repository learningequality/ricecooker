import unittest

from ricecooker.utils import downloader


class TestArchiver(unittest.TestCase):
    def test_get_archive_filename_absolute(self):
        link = 'https://learningequality.org/kolibri.png'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, download_root='./', resource_urls=urls_to_replace)

        assert result == 'learningequality.org/kolibri.png'
        assert urls_to_replace[link] == 'learningequality.org/kolibri.png'

    def test_get_archive_filename_relative(self):
        link = '../kolibri.png'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', resource_urls=urls_to_replace)

        assert result == 'learningequality.org/kolibri.png'
        assert urls_to_replace[link] == 'learningequality.org/kolibri.png'

    def test_get_archive_filename_with_query(self):
        link = '../kolibri.png?1.2.3'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', resource_urls=urls_to_replace)

        assert result == 'learningequality.org/kolibri_1.2.3.png'
        assert urls_to_replace[link] == 'learningequality.org/kolibri_1.2.3.png'

        link = '../kolibri.png?v=1.2.3&i=u'
        page_link = 'https://learningequality.org/team/index.html'

        urls_to_replace = {}
        result = downloader.get_archive_filename(link, page_url=page_link,
                                        download_root='./', resource_urls=urls_to_replace)

        assert result == 'learningequality.org/kolibri_v_1.2.3_i_u.png'
        assert urls_to_replace[link] == 'learningequality.org/kolibri_v_1.2.3_i_u.png'
