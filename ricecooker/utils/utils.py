import hashlib
import os
import re
import shutil
from urllib.parse import urlparse

from ricecooker import config


VALID_UUID_REGEX = re.compile("^([a-f0-9]{32})$")


def is_valid_uuid_string(uuid_str):
    """
    Check if a string is a valid UUID.
    """
    return isinstance(uuid_str, str) and VALID_UUID_REGEX.match(uuid_str)


def make_dir_if_needed(path):
    """
    Check if the dir exists, and if not, create it. If the directory exists, just return it
    rather than throwing an error.

    :param path: A string representing a directory on disk.
    :return: A path to the directory that is guaranteed to exist.
    """

    if not os.path.exists(path):
        os.makedirs(path)
    return path


class VideoURLFormatError(Exception):
    def __init__(self, url, expected_format):
        self.message = (
            "The video at {} does not appear to be a proper {} video URL.".format(
                url, expected_format
            )
        )


def extract_path_ext(path, default_ext=None):
    """
    Extract file extension (without dot) from `path` or return `default_ext` if
    path does not contain a valid extension.
    """
    path = urlparse(path).path
    _, ext = os.path.splitext(path)
    # Remove the leading "." from the extension
    ext = ext[1:] if ext else ext
    if not ext and default_ext:
        ext = default_ext
    if not ext:
        raise ValueError("No extension in path {} and default_ext is None".format(path))
    return ext.lower()


def get_hash(filepath):
    file_hash = hashlib.md5()
    with open(filepath, "rb") as fobj:
        for chunk in iter(lambda: fobj.read(2097152), b""):
            file_hash.update(chunk)
    return file_hash.hexdigest()


def is_valid_url(path):
    """
    Return `True` if path is a valid URL, else `False` if path is a local path.
    """
    parts = urlparse(path)
    return parts.scheme != "" and parts.netloc != ""


def copy_file_to_storage(srcfilename, ext=None):
    """
    Copy `srcfilename` (filepath) to destination.
    :rtype: None
    """
    if ext is None:
        ext = extract_path_ext(srcfilename)

    hash = get_hash(srcfilename)
    filename = "{}.{}".format(hash, ext)
    try:
        shutil.copy(srcfilename, config.get_storage_path(filename))
    except shutil.SameFileError:
        return filename

    return filename
