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
            session (Session): session to handle requests
            all_file_extensions ([str]): all accepted file extensions
            files ([str]): files that have been downloaded by download manager
            _file_mapping ([{'filename':{...}]): map from filename to file metadata
    """

    # All accepted file extensions
    all_file_extensions = [key for key, value in file_formats.choices]

    def __init__(self, file_store):
        self.file_store = {}
        if os.stat(file_store).st_size > 0:
            with open(file_store, 'r') as jsonobj:
                self.file_store = json.load(jsonobj)

        self.files = []
        self.failed_files = []

    def get_files(self):
        """ get_files: get files downloaded by download manager
            Args:None
            Returns: list of downloaded files
        """
        return self.files

    def get_filenames(self):
        """ get_filenames: get filenames downloaded by download manager
            Args:None
            Returns: list of downloaded filenames
        """
        return [f.filename for f in self.files]

    def has_failed_files(self):
        """ has_failed_files: check if any files have failed
            Args: None
            Returns: boolean indicating if files have failed
        """
        return len(self.failed_files) > 0

    def print_failed(self):
        """ print_failed: print out files that have failed downloading
            Args: None
            Returns: None
        """
        config.LOGGER.warning("   WARNING: The following files could not be accessed:")
        for f in self.failed_files:
            config.LOGGER.warning("\t{0} {id}: {path} \n\t   {err}".format(f.node.kind.capitalize(), id=f.node.original_id, path=f.path, err=f.error))

    def check_downloaded_file(self, file_model):
        """ check_downloaded_file: determine if file has been downloaded before
            Args:
                file_model (File): file to check for in cache
            Returns: boolean indicating if the file has been downloaded before
        """
        return not config.UPDATE and file_model.cache_key in self.file_store

    def add_to_downloaded(self, file_model, track_file=True):
        """ add_to_downloaded: add file to list of files downloaded this session
            Args:
                file_model (File): file to add
            Returns:
        """
        if track_file:
            self.files.append(file_model)
        if file_model.cache_key is not None:
            self.file_store.update({file_model.cache_key:{
                'file_size' : file_model.file_size,
                'filename' : file_model.filename,
                'original_filename' : file_model.original_filename,
            }})

    def add_to_failed(self, file_model):
        """ add_to_failed: add file to list of files that failed to download this session
            Args:
                file_model (File): file to add
            Returns:
        """
        self.failed_files.append(file_model)

    def handle_existing_file(self, file_model, track_file=True):
        """ handle_existing_file: add file to mapping if already downloaded
            Args:
                path (str): url or path to file to track
            Returns: file data for tracked file
        """
        data = self.file_store[file_model.cache_key]
        file_model.map_from_downloaded(data)

        if track_file:
            self.files.append(file_model)
