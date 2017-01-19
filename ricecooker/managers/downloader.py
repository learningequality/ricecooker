import hashlib
import json
import requests
import base64
import tempfile
import shutil
import os
import sys
import requests
from enum import Enum
from pressurecooker.videos import extract_thumbnail_from_video, check_video_resolution, compress_video
from pressurecooker.encodings import get_base64_encoding, write_base64_to_file
from .. import config
from ..exceptions import InvalidFormatException, FileNotFoundException
from le_utils.constants import file_formats, exercises, format_presets

class DownloadManager:
    """ Manager for handling file downloading and storage

        Attributes:
            all_file_extensions ([str]): all accepted file extensions
            files ([str]): files that have been downloaded by download manager
    """

    # All accepted file extensions
    all_file_extensions = [key for key, value in file_formats.choices]

    def __init__(self, file_store):
        self.file_store = {}
        if os.stat(file_store).st_size > 0:
            with open(file_store, 'r') as jsonobj:
                self.file_store = json.load(jsonobj)

    def get(self, key):
        return self.file_store.get(key)

    def set(self, key, value):
        self.file_store.update({key: value})
        config.set_file_store(self.file_store)
