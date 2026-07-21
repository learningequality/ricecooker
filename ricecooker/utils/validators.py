import re
from urllib.parse import urlparse

VALID_UUID_REGEX = re.compile("^([a-f0-9]{32})$")


def is_valid_uuid_string(uuid_str):
    """
    Check if a string is a valid UUID.
    """
    return isinstance(uuid_str, str) and VALID_UUID_REGEX.match(uuid_str)


def is_valid_url(path):
    """
    Return `True` if path is a valid URL, else `False` if path is a local path.
    """
    parts = urlparse(path)
    return parts.scheme != "" and parts.netloc != ""
