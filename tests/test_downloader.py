import os
import unittest
import timeit
import requests
import ricecooker
import pytest

from ricecooker.utils import downloader
from ricecooker.utils.downloader import make_request
from ricecooker.utils.downloader import configure_download_session


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


def test_useragent_generation():

    session_no_email = requests.Session()
    configure_download_session(session_no_email)
    expected_no_email = f"Ricecooker/{ricecooker.__version__} bot (no-reply@ricecooker.org)"
    assert session_no_email.headers['User-Agent'] == expected_no_email

    session_with_email = requests.Session()
    test_email = "test_user@example.com"
    configure_download_session(session_with_email, user_email=test_email)
    expected_with_email = f"Ricecooker/{ricecooker.__version__} bot ({test_email})"
    assert session_with_email.headers['User-Agent'] == expected_with_email


def test_request_retry_logic():
    unreliable_url = "http://non-existent-url.test"

    with pytest.raises(requests.exceptions.RequestException):
        make_request(
            unreliable_url,
            user_email="retry_test@example.com",
            timeout=1
        )


def test_performance_overhead():
    """
    Measure performance impact of User-Agent header generation
    """


def baseline_request():
    make_request("https://example.com")


def custom_email_request():
    make_request("https://example.com", user_email="perf_test@example.com")


baseline_time = timeit.timeit(baseline_request, number=100)
custom_email_time = timeit.timeit(custom_email_request, number=100)

assert custom_email_time - baseline_time < 0.01


def test_useragent_content_validation():
    """
    Comprehensive validation of User-Agent header contents
    """
    session = requests.Session()
    test_email = "validator@example.com"
    configure_download_session(session, user_email=test_email)

    user_agent = session.headers['User-Agent']

    # Validation checks
    assert "Ricecooker/" in user_agent
    assert ricecooker.__version__ in user_agent
    assert test_email in user_agent
    assert user_agent.startswith("Ricecooker/")
    assert "bot" in user_agent
