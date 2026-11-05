import functools
import os
import threading
from http.client import RemoteDisconnected
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from requests.utils import rewind_body
from urllib3.exceptions import MaxRetryError
from urllib3.exceptions import ProtocolError
from urllib3.exceptions import ProxyError


class DomainSpecificAuth(AuthBase):
    """
    Selects the appropriate authentication headers based on the request URL.
    """

    def __init__(self, domain_to_headers):
        """
        Args:
            domain_to_headers (dict): mapping of domain (str) to headers (dict)
            the headers values are names of environment variables to read the actual values from
            in order to avoid hardcoding sensitive information in code or config files
        """
        self.domain_to_headers = self._process_domain_haders(domain_to_headers)

    def _process_domain_haders(self, domain_to_headers):
        """
        Process the domain_to_headers to ensure all header keys are strings and read values from environment variables.
        Args:
            domain_to_headers (dict): mapping of domain (str) to headers (dict)
        Returns:
            processed_domain_to_headers (dict): mapping of domain (str) to headers (dict with str keys)
        """
        processed_domain_to_headers = {}
        for domain, headers in domain_to_headers.items():
            processed_headers = {}
            for key, value in headers.items():
                new_value = os.environ.get(str(value))
                if not new_value:
                    raise ValueError(
                        f"Environment variable for header value '{value}' not set."
                    )
                processed_headers[str(key)] = new_value
            processed_domain_to_headers[domain] = processed_headers
        return processed_domain_to_headers

    def __call__(self, r):
        """
        Args:
            r: (requests.PreparedRequest)
        Returns:
            r: (requests.PreparedRequest)
        """
        headers = self.domain_to_headers.get(urlparse(r.url).netloc, {})
        r.domain_auth = self
        r.domain_auth_replaced = {
            key: (r.headers.get(key), value) for key, value in headers.items()
        }
        r.headers.update(headers)
        return r

    def rebuild(self, r, previous):
        for key, (replaced, added) in previous.domain_auth_replaced.items():
            if r.headers.get(key) != added:
                continue
            if replaced is None:
                del r.headers[key]
            else:
                r.headers[key] = replaced
        if (
            urlparse(previous.url).scheme == "https"
            and urlparse(r.url).scheme == "http"
        ):
            return r
        return self(r)


class DomainAuthSession(requests.Session):
    """requests strips only Authorization on redirect, so other domain headers would follow to the new host."""

    def rebuild_auth(self, prepared_request, response):
        super().rebuild_auth(prepared_request, response)
        auth = getattr(response.request, "domain_auth", None)
        if auth is not None:
            auth.rebuild(prepared_request, response.request)


_last_connection = threading.local()


def _is_remote_disconnect(error):
    reason = error.args[0] if error.args else None
    if isinstance(reason, MaxRetryError):
        reason = reason.reason
    return isinstance(reason, (ProtocolError, ProxyError)) and any(
        isinstance(arg, RemoteDisconnected) for arg in reason.args
    )


class _ReuseTrackingPoolMixin:
    def _get_conn(self, timeout=None):
        conn = super()._get_conn(timeout)
        _last_connection.reused = conn.sock is not None
        return conn


@functools.cache
def _reuse_tracking(pool_class):
    return type(
        f"ReuseTracking{pool_class.__name__}", (_ReuseTrackingPoolMixin, pool_class), {}
    )


def _track_reuse(manager):
    manager.pool_classes_by_scheme = {
        scheme: _reuse_tracking(pool_class)
        for scheme, pool_class in manager.pool_classes_by_scheme.items()
    }


class ReconnectingAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        _track_reuse(self.poolmanager)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        fresh = proxy not in self.proxy_manager
        manager = super().proxy_manager_for(proxy, **proxy_kwargs)
        if fresh:
            _track_reuse(manager)
        return manager

    def send(self, request, **kwargs):
        rewindable = isinstance(request._body_position, int)
        resendable = (
            rewindable or request.body is None or isinstance(request.body, (bytes, str))
        )
        while True:
            _last_connection.reused = False
            try:
                return super().send(request, **kwargs)
            except requests.ConnectionError as e:
                if not (
                    resendable and _last_connection.reused and _is_remote_disconnect(e)
                ):
                    raise
                if rewindable:
                    rewind_body(request)
