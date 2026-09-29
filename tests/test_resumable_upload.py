import io

import pytest
from requests.exceptions import ConnectionError
from requests.exceptions import RequestException

from ricecooker.utils.resumable_upload import _query_offset
from ricecooker.utils.resumable_upload import MAX_RESUME_ATTEMPTS
from ricecooker.utils.resumable_upload import resumable_upload


class FakeResponse:
    def __init__(self, status_code, body=b"", headers=None):
        self.status_code = status_code
        self.content = body
        self.text = body.decode() if isinstance(body, bytes) else body
        self.headers = headers or {}


def _is_status_query(headers):
    """A status-query PUT sends `Content-Range: bytes */{total}` (no byte range)."""
    return "*/" in headers["Content-Range"]


class FakeSession:
    """Fake session that answers chunk PUTs and status-query PUTs from separate
    canned-response queues, distinguishing them by their Content-Range header.
    """

    def __init__(self, chunk_responses=(), query_responses=()):
        self.chunk_responses = list(chunk_responses)
        self.query_responses = list(query_responses)
        self.calls = []

    def put(self, url, data=None, headers=None, allow_redirects=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "data": data,
                "headers": headers,
                "allow_redirects": allow_redirects,
                "timeout": timeout,
            }
        )
        queue = (
            self.query_responses if _is_status_query(headers) else self.chunk_responses
        )
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            status_code, headers_out = response
            return FakeResponse(status_code, headers=headers_out)
        return FakeResponse(response)


SESSION_URI = "https://upload.example.com/session/abc123"


def test_single_chunk_completes():
    content = b"x" * 100
    session = FakeSession([200])
    file_obj = io.BytesIO(content)

    resumable_upload(session, SESSION_URI, file_obj, total_size=len(content))

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["headers"]["Content-Range"] == "bytes 0-99/100"
    assert call["data"] == content


def test_multiple_chunks_use_308_then_200():
    chunk_size = 1000
    total_size = chunk_size + 100
    content = bytes(range(256)) * ((total_size // 256) + 1)
    content = content[:total_size]
    session = FakeSession([(308, {"Range": f"bytes=0-{chunk_size - 1}"}), 200])
    file_obj = io.BytesIO(content)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )

    assert len(session.calls) == 2

    first_call = session.calls[0]
    assert (
        first_call["headers"]["Content-Range"]
        == f"bytes 0-{chunk_size - 1}/{total_size}"
    )
    assert first_call["data"] == content[0:chunk_size]

    second_call = session.calls[1]
    assert (
        second_call["headers"]["Content-Range"]
        == f"bytes {chunk_size}-{total_size - 1}/{total_size}"
    )
    assert second_call["data"] == content[chunk_size:total_size]


def test_zero_byte_file():
    session = FakeSession(query_responses=[200])
    file_obj = io.BytesIO(b"")

    resumable_upload(session, SESSION_URI, file_obj, total_size=0)

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["headers"]["Content-Range"] == "bytes */0"
    assert call["data"] == b""


def test_allow_redirects_false():
    chunk_size = 1000
    total_size = chunk_size + 100
    content = b"y" * total_size
    session = FakeSession([(308, {"Range": f"bytes=0-{chunk_size - 1}"}), 200])
    file_obj = io.BytesIO(content)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )

    assert len(session.calls) == 2
    for call in session.calls:
        assert call["allow_redirects"] is False


def test_unexpected_status_raises():
    content = b"z" * 100
    session = FakeSession([403])
    file_obj = io.BytesIO(content)

    with pytest.raises(RequestException):
        resumable_upload(session, SESSION_URI, file_obj, total_size=len(content))


def test_308_range_header_sets_next_offset():
    chunk_size = 1000
    total_size = chunk_size + 100
    content = b"y" * total_size
    n = chunk_size - 400  # server persisted less than the full chunk
    session = FakeSession([(308, {"Range": f"bytes=0-{n}"}), 200])
    file_obj = io.BytesIO(content)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )

    assert len(session.calls) == 2
    second_call = session.calls[1]
    assert (
        second_call["headers"]["Content-Range"]
        == f"bytes {n + 1}-{total_size - 1}/{total_size}"
    )
    assert second_call["data"] == content[n + 1 : total_size]


def test_308_without_range_header_restarts_from_zero():
    chunk_size = 1000
    total_size = chunk_size + 100
    content = bytes(range(256)) * ((total_size // 256) + 1)
    content = content[:total_size]
    session = FakeSession([308, 200])
    file_obj = io.BytesIO(content)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )

    assert len(session.calls) == 2
    second_call = session.calls[1]
    assert (
        second_call["headers"]["Content-Range"]
        == f"bytes 0-{chunk_size - 1}/{total_size}"
    )
    assert second_call["data"] == content[0:chunk_size]


def test_resumes_after_connection_error():
    chunk_size = 1000
    total_size = chunk_size + 100
    content = bytes(range(256)) * ((total_size // 256) + 1)
    content = content[:total_size]
    k = 500
    session = FakeSession(
        chunk_responses=[ConnectionError("boom"), 200],
        query_responses=[(308, {"Range": f"bytes=0-{k}"})],
    )
    file_obj = io.BytesIO(content)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )

    assert len(session.calls) == 3

    status_query_call = session.calls[1]
    assert status_query_call["headers"]["Content-Range"] == f"bytes */{total_size}"

    resumed_call = session.calls[2]
    assert (
        resumed_call["headers"]["Content-Range"]
        == f"bytes {k + 1}-{total_size - 1}/{total_size}"
    )
    assert resumed_call["data"] == content[k + 1 : total_size]


def test_resumes_after_offset_query_connection_error():
    chunk_size = 1000
    total_size = chunk_size + 100
    content = bytes(range(256)) * ((total_size // 256) + 1)
    content = content[:total_size]
    k = 500
    session = FakeSession(
        chunk_responses=[ConnectionError("boom"), 200],
        query_responses=[
            ConnectionError("still down"),
            (308, {"Range": f"bytes=0-{k}"}),
        ],
    )
    file_obj = io.BytesIO(content)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )

    resumed_call = session.calls[-1]
    assert (
        resumed_call["headers"]["Content-Range"]
        == f"bytes {k + 1}-{total_size - 1}/{total_size}"
    )
    assert resumed_call["data"] == content[k + 1 : total_size]


def test_gives_up_after_max_attempts():
    content = b"z" * 100
    # Every chunk PUT fails; status queries between attempts succeed, so the
    # loop keeps retrying until the failure counter exceeds MAX_RESUME_ATTEMPTS.
    session = FakeSession(
        chunk_responses=[ConnectionError("boom")] * (MAX_RESUME_ATTEMPTS + 1),
        query_responses=[(308, {"Range": "bytes=0-0"})] * MAX_RESUME_ATTEMPTS,
    )
    file_obj = io.BytesIO(content)

    with pytest.raises(RequestException):
        resumable_upload(session, SESSION_URI, file_obj, total_size=len(content))

    chunk_attempts = sum(
        1 for call in session.calls if not _is_status_query(call["headers"])
    )
    assert chunk_attempts == MAX_RESUME_ATTEMPTS + 1


def test_expired_session_on_offset_query_raises_without_retrying():
    content = b"z" * 100
    session = FakeSession(
        chunk_responses=[ConnectionError("boom")],
        query_responses=[404],
    )
    file_obj = io.BytesIO(content)

    with pytest.raises(RequestException):
        resumable_upload(session, SESSION_URI, file_obj, total_size=len(content))

    assert len(session.calls) == 2


def test_every_put_has_a_timeout():
    chunk_size = 1000
    total_size = chunk_size + 100
    session = FakeSession(
        chunk_responses=[ConnectionError("boom"), 200],
        query_responses=[(308, {"Range": f"bytes=0-{chunk_size - 1}"})],
    )
    file_obj = io.BytesIO(b"y" * total_size)

    resumable_upload(
        session, SESSION_URI, file_obj, total_size=total_size, chunk_size=chunk_size
    )
    empty_session = FakeSession(query_responses=[200])
    resumable_upload(empty_session, SESSION_URI, io.BytesIO(b""), total_size=0)

    assert all(call["timeout"] for call in session.calls + empty_session.calls)


def test_query_offset_no_range_returns_zero():
    session = FakeSession(query_responses=[308])
    offset = _query_offset(session, SESSION_URI, total_size=100)

    assert offset == 0
    assert len(session.calls) == 1
    assert session.calls[0]["headers"]["Content-Range"] == "bytes */100"
    assert session.calls[0]["allow_redirects"] is False


def test_upload_session_retries_5xx_and_is_separate_from_studio_session():
    from ricecooker import config

    adapter = config.UPLOAD_SESSION.get_adapter("https://storage.googleapis.com/x")
    assert 503 in adapter.max_retries.status_forcelist
    assert config.UPLOAD_SESSION is not config.SESSION
