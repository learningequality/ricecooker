import os
import re


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
