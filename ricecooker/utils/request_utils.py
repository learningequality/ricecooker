import os
from urllib.parse import urlparse

from requests.auth import AuthBase


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
        domain = urlparse(r.url).netloc
        if domain in self.domain_to_headers:
            r.headers.update(self.domain_to_headers[domain])
        return r
