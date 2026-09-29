from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import requests

from ricecooker import config


@contextmanager
def fake_download_session(url_to_content):
    """Patch the pipeline's HTTP session so external refs resolve to fixed bytes.

    Only the network boundary is mocked; the real ``FilePipeline`` still runs each
    reference through download -> convert. An unmapped URL raises like a failed
    request, so tests exercise the leave-unrewritten path too. Yields the list of
    fetched URLs for call assertions.
    """
    calls = []

    def get(url, stream=True, timeout=None):
        calls.append(url)
        if url not in url_to_content:
            raise requests.exceptions.ConnectionError("no fake resource for " + url)
        content = url_to_content[url]
        return SimpleNamespace(
            headers={},
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size=8192: iter([content]),
        )

    def head(url, **kwargs):
        # The render handler HEAD-probes every external ref to see if it is an
        # HTML page; these fixtures are assets, so report a non-HTML type and let
        # the catch-all download handler fetch them via get().
        return SimpleNamespace(headers={"content-type": "application/octet-stream"})

    with patch.object(config, "DOWNLOAD_SESSION", SimpleNamespace(get=get, head=head)):
        yield calls
