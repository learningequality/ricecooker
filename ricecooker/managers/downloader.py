import json
import os
from .. import config

class DownloadManager:
    """ Manager for handling file downloading and storage

        Attributes:
            all_file_extensions ([str]): all accepted file extensions
            files ([str]): files that have been downloaded by download manager
    """

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
