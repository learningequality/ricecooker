"""Client for the GCS resumable upload protocol used by Kolibri Studio.

Uploads a file to an already-initiated resumable upload session in sequential
chunks. Studio bakes integrity metadata (md5, content-type) into the session
at creation time, so chunk PUTs carry no `Content-Type`, `x-goog-hash`, or
auth headers of their own.
"""

import re

from requests.exceptions import HTTPError
from requests.exceptions import RequestException

CHUNK_SIZE = 8 * 1024 * 1024

MAX_RESUME_ATTEMPTS = 5

TIMEOUT = (30, 120)

_RANGE_RE = re.compile(r"bytes=\d+-(\d+)")


def _next_offset(response):
    # GCS omits Range from a 308 when it has persisted no bytes.
    match = _RANGE_RE.match(response.headers.get("Range", ""))
    return int(match.group(1)) + 1 if match else 0


def _put(session, session_uri, data, content_range):
    return session.put(
        session_uri,
        data=data,
        headers={"Content-Range": content_range},
        allow_redirects=False,
        timeout=TIMEOUT,
    )


def _unexpected_status(response, action, session_uri):
    return HTTPError(
        f"Unexpected status {response.status_code} {action} {session_uri}: {response.text}",
        response=response,
    )


def _query_offset(session, session_uri, total_size):
    """Ask GCS how many bytes of `session_uri` it has persisted so far.

    :param session: object exposing a `requests`-compatible `.put()`.
    :param session_uri: GCS resumable session URI to query.
    :param total_size: total size of the file in bytes.
    :return: next byte offset the caller should send from.
    :raises requests.exceptions.HTTPError: on any unexpected status.
    """
    response = _put(session, session_uri, b"", f"bytes */{total_size}")

    if response.status_code == 308:
        return _next_offset(response)
    if response.status_code in (200, 201):
        return total_size
    raise _unexpected_status(response, "querying offset for", session_uri)


def resumable_upload(session, session_uri, file_obj, total_size, chunk_size=CHUNK_SIZE):
    """Upload `file_obj` to `session_uri` via sequential chunked PUTs.

    Tolerates transport-level failures (after the session's `Retry` adapter's
    own retries are exhausted) by re-querying the server-persisted offset and
    resuming from there, up to `MAX_RESUME_ATTEMPTS` consecutive failures.

    :param session: object exposing a `requests`-compatible `.put()`.
    :param session_uri: GCS resumable session URI to PUT chunks to.
    :param file_obj: seekable binary stream to read chunks from.
    :param total_size: total size of the file in bytes.
    :param chunk_size: max bytes to send per PUT.
    :raises requests.exceptions.HTTPError: on any unexpected status.
    :raises requests.exceptions.RequestException: after `MAX_RESUME_ATTEMPTS`
        consecutive transport failures.
    """
    if total_size == 0:
        response = _put(session, session_uri, b"", "bytes */0")
        if response.status_code in (200, 201):
            return
        raise _unexpected_status(response, "uploading", session_uri)

    start = 0
    consecutive_failures = 0
    resync = False
    while start < total_size:
        try:
            if resync:
                start = _query_offset(session, session_uri, total_size)
                resync = False
                continue
            file_obj.seek(start)
            chunk = file_obj.read(chunk_size)
            end = start + len(chunk) - 1
            response = _put(
                session, session_uri, chunk, f"bytes {start}-{end}/{total_size}"
            )
        except HTTPError:
            raise
        except RequestException:
            consecutive_failures += 1
            if consecutive_failures > MAX_RESUME_ATTEMPTS:
                raise
            resync = True
            continue

        if response.status_code == 308:
            consecutive_failures = 0
            start = _next_offset(response)
            continue
        if response.status_code in (200, 201):
            return
        raise _unexpected_status(response, "uploading", session_uri)
