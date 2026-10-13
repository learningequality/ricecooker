from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import requests

from ricecooker import config


@contextmanager
def fake_download_session(url_to_content, content_types=None):
    """Patch the pipeline's HTTP session so external refs resolve to fixed bytes.

    Only the network boundary is mocked; the real ``FilePipeline`` still runs each
    reference through download -> convert. An unmapped URL raises like a failed
    request, so tests exercise the leave-unrewritten path too. Yields the list of
    fetched URLs for call assertions.

    A URL maps to bytes, to an exception ``get`` raises, or to a list of chunks
    where an exception element is raised when the body stream reaches it.
    ``content_types`` maps a URL to the Content-Type its response carries.
    """
    calls = []
    content_types = content_types or {}

    def iter_chunks(chunks):
        for chunk in chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def get(url, stream=True, timeout=None):
        calls.append(url)
        if url not in url_to_content:
            raise requests.exceptions.ConnectionError("no fake resource for " + url)
        content = url_to_content[url]
        if isinstance(content, Exception):
            raise content
        chunks = content if isinstance(content, list) else [content]
        headers = {"content-type": content_types[url]} if url in content_types else {}
        return SimpleNamespace(
            headers=headers,
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size=8192: iter_chunks(chunks),
        )

    def head(url, **kwargs):
        return SimpleNamespace(
            ok=True,
            headers={
                "content-type": content_types.get(url, "application/octet-stream")
            },
        )

    with patch.object(config, "DOWNLOAD_SESSION", SimpleNamespace(get=get, head=head)):
        yield calls
