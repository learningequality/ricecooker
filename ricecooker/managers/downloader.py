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
from requests.exceptions import MissingSchema, HTTPError, ConnectionError, InvalidURL, InvalidSchema
from .. import config
from ..exceptions import InvalidFormatException, FileNotFoundException
from le_utils.constants import file_formats, exercises, format_presets

class DownloadManager:
    """ Manager for handling file downloading and storage

        Attributes:
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
        self._file_mapping = {} # Used to keep track of files and their respective metadata

    def get_files(self):
        """ get_files: get files downloaded by download manager
            Args:None
            Returns: list of downloaded files
        """
        return self.files

    def get_file_mapping(self):
        """ get_file_mapping: get file metadata
            Args:None
            Returns: dict of file metadata
        """
        return self._file_mapping

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
            config.LOGGER.warning("\t{id}: {path}".format(id=f[1], path=f[0]))

    def download_graphie(self, path, title):
        """ download_graphie: download a web+graphie file
            Args:
                path (str): path to .svg and .json files
                title (str): node to print if download fails
            Returns: file data for .graphie file (combination of svg and json files)
        """
        # Handle if path has already been processed
        if exercises.CONTENT_STORAGE_PLACEHOLDER in path:
            filename = os.path.split(path)[-1]
            return filename, filename + ".svg", filename + "-data.json"

        # Initialize paths and hash
        svg_path = path + ".svg"
        json_path = path + "-data.json"
        path_name = svg_path + ' & ' + json_path
        hash = hashlib.md5()
        original_filename = path.split("/")[-1].split(".")[0]
        delimiter = bytes(exercises.GRAPHIE_DELIMITER, 'UTF-8')

        # Track file if it's already in the downloaded file list
        if self.check_downloaded_file(path_name):
            return self.track_existing_file(path_name)

        try:
            # Create graphie file combining svg and json files
            with tempfile.TemporaryFile() as tempf:
                config.LOGGER.info("\tDownloading graphie {}".format(original_filename))

                # Write to graphie file
                self.write_to_graphie_file(svg_path, tempf, hash)
                tempf.write(delimiter)
                hash.update(delimiter)
                self.write_to_graphie_file(json_path, tempf, hash)

                # Extract file metadata
                file_size = tempf.tell()
                tempf.seek(0)
                filename = '{0}.{ext}'.format(hash.hexdigest(), ext=file_formats.GRAPHIE)

                # If file already exists, skip it
                if os.path.isfile(config.get_storage_path(filename)):
                    config.LOGGER.info("\t--- No changes detected on {0}".format(filename))
                    # Keep track of downloaded file
                    self.track_file(filename, file_size, format_presets.EXERCISE_GRAPHIE, path_name, original_filename)
                    return self._file_mapping[filename]

                # Write file to local storage
                with open(config.get_storage_path(filename), 'wb') as destf:
                    shutil.copyfileobj(tempf, destf)

                # Keep track of downloaded file
                self.track_file(filename, file_size, format_presets.EXERCISE_GRAPHIE, path_name, original_filename)
                config.LOGGER.info("\t--- Downloaded {}".format(filename))
                return self._file_mapping[filename]

        # Catch errors related to reading file path and handle silently
        except (HTTPError, ConnectionError, InvalidURL, InvalidSchema, IOError):
            self.failed_files += [(path,title)]
            return False;
        except (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError):
            self.failed_files += [(path, title)]
            return False

    def write_to_graphie_file(self, path, tempf, hash):
        """ write_to_graphie_file: write from path to graphie file
            Args:
                path (str): path to file to read from
                tempf (TemporaryFile): file to write to
                hash (md5): hash to update during write process
            Returns: None
        """
        try:
            r = config.SESSION.get(path, stream=True)
            r.raise_for_status()
            for chunk in r:
                tempf.write(chunk)
                hash.update(chunk)
        except (MissingSchema, InvalidSchema):
            # Try opening path as relative file path
            with open(path, 'rb') as file_obj:
                for chunk in iter(lambda: file_obj.read(4096), b""):
                    hash.update(chunk)
                    tempf.write(chunk)

    def get_hash(self, path):
        """ get_hash: generate hash of file
            Args:
                path (str): url or path to file to get hash from
            Returns: md5 hash of file
        """
        hash_to_update = hashlib.md5()
        try:
            r = config.SESSION.get(path, stream=True)
            r.raise_for_status()
            for chunk in r:
                hash_to_update.update(chunk)
        except (MissingSchema, InvalidSchema):
            with open(path, 'rb') as fobj:
                for chunk in iter(lambda: fobj.read(4096), b""):
                    hash_to_update.update(chunk)

        return hash_to_update

    def check_downloaded_file(self, path):
        """ check_downloaded_file: determine if file has been downloaded before
            Args:
                path (str): url or path to file to check
            Returns: boolean indicating if the file has been downloaded before
        """
        return not config.UPDATE and path in self.file_store

    def track_existing_file(self, path):
        """ track_existing_file: add file to mapping if already downloaded
            Args:
                path (str): url or path to file to track
            Returns: file data for tracked file
        """
        data = self.file_store[path]
        config.LOGGER.info("\tFile {0} already exists (add '-u' flag to update)".format(data['filename']))
        self.track_file(data['filename'], data['size'],  data.get('preset'), original_filename=data.get('original_filename'), extracted=data.get("extracted"))
        return self._file_mapping[data['filename']]

    def download_file(self, path, title, default_ext=None, preset=None, extracted=False, original_filepath=None):
        """ download_file: downloads file from path
            Args:
                path (str): local path or url to file to download
                title (str): node to print if download fails
                default_ext (str): extension to use if none given (optional)
                preset (str): preset to use (optional)
            Returns: filename of downloaded file
        """
        try:
            # Handle if path has already been processed
            if exercises.CONTENT_STORAGE_PLACEHOLDER in path:
                return self._file_mapping[os.path.split(path)[-1]]

            if not original_filepath:
                original_filepath = path

            if self.check_downloaded_file(original_filepath):
                return self.track_existing_file(original_filepath)

            if get_base64_encoding(path):
                return self.convert_base64_to_file(path, title, preset=preset)

            config.LOGGER.info("\tDownloading {}".format(path))

            hash=self.get_hash(path)

            # Get extension of file or default if none found
            extension = os.path.splitext(path)[1][1:].lower()
            if extension not in self.all_file_extensions:
                if default_ext is not None:
                    extension = default_ext
                else:
                    raise IOError("No extension found: {}".format(path))

            filename = '{0}.{ext}'.format(hash.hexdigest(), ext=extension)

            # If file already exists, skip it
            if os.path.isfile(config.get_storage_path(filename)):
                config.LOGGER.info("\t--- No changes detected on {0}".format(filename))

                if extension == file_formats.MP4:
                    preset = check_video_resolution(config.get_storage_path(filename))

                # Keep track of downloaded file
                self.track_file(filename, os.path.getsize(config.get_storage_path(filename)), preset, path, extracted=extracted)
                return self._file_mapping[filename]

            # Write file to temporary file
            with tempfile.TemporaryFile() as tempf:
                try:
                    # Access path
                    r = config.SESSION.get(path, stream=True)
                    r.raise_for_status()

                    # Write to file (generate hash if none provided)
                    for chunk in r:
                        tempf.write(chunk)

                except (MissingSchema, InvalidSchema):
                    # If path is a local file path, try to open the file (generate hash if none provided)
                    with open(path, 'rb') as fobj:
                        tempf.write(fobj.read())

                # Get file metadata (hashed filename, original filename, size)
                file_size = tempf.tell()
                tempf.seek(0)

                # Write file to local storage
                with open(config.get_storage_path(filename), 'wb') as destf:
                    shutil.copyfileobj(tempf, destf)

                # If a video file, check its resolution
                if extension == file_formats.MP4:
                    preset = check_video_resolution(config.get_storage_path(filename))

                # Keep track of downloaded file
                self.track_file(filename, file_size, preset, original_filepath, extracted=extracted)
                config.LOGGER.info("\t--- Downloaded {}".format(filename))
                return self._file_mapping[filename]

        # Catch errors related to reading file path and handle silently
        except (HTTPError, ConnectionError, InvalidURL, UnicodeDecodeError, UnicodeError, InvalidSchema, IOError):
            self.failed_files += [(path,title)]
            return False;

    def track_file(self, filename, file_size, preset, path=None, original_filename='[File]', extracted=False):
        """ track_file: record which file has been downloaded along with metadata
            Args:
                filename (str): name of file to track
                file_size (int): size of file
                preset (str): preset to assign to file
                path (str): source path of file (optional)
                original_filename (str): file's original name (optional)
                extracted (bool): indicates whether file has been extracted automatically (optional)
            Returns: None
        """
        self.files += [filename]
        file_data = {
            'size' : file_size,
            'preset' : preset,
            'filename' : filename,
            'original_filename' : original_filename,
            'extracted' : extracted,
        }
        self._file_mapping.update({filename : file_data})

        if path is not None:
            self.file_store.update({path:file_data})

    def download_files(self,files, title, default_ext=None):
        """ download_files: download list of files
            Args:
                files ([str]): list of file paths or urls to download
                title (str): name of node in case of error
                default_ext (str): extension to use if none is provided (optional)
            Returns: list of downloaded filenames
        """
        file_list = []
        for f in files:
            file_data = f.split('/')[-1]
            result = self.download_file(f, title, default_ext=default_ext)
            if result:
                file_list += [result]
        return file_list

    def derive_thumbnail(self, filepath, title):
        """ derive_thumbnail: derive video's thumbnail
            Args:
                filepath (str): path to video file
                title (str): name of node in case of error
            Returns: None
        """
        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG)) as tempf:
            tempf.close()
            extract_thumbnail_from_video(filepath, tempf.name, overwrite=True)
            return self.download_file(tempf.name, title, extracted=True, original_filepath=filepath + " (thumbnail)")

    def compress_file(self, filepath, title):
        """ compress_file: compress the video to a lower resolution
            Args:
                filepath (str): path to video file
                title (str): name of node in case of error
            Returns: None
        """
        # If file has already been compressed, return the compressed file data
        if self.check_downloaded_file(filepath) and self.file_store[filepath].get('extracted'):
            config.LOGGER.info("\tFound compressed file for {}".format(filepath))
            return self.track_existing_file(filepath)

        # Otherwise, compress the file
        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.MP4)) as tempf:
            tempf.close()
            compress_video(filepath, tempf.name, overwrite=True)
            return self.download_file(tempf.name, title, extracted=True, original_filepath=filepath)

    def convert_base64_to_file(self, text, title, preset=None):
        """ convert_base64_to_file: Writes base64 encoding to file
            Args:
                text (str): text to parse
            Returns: dict of file data
        """
        # Get hash of content for tracking purposes
        hashed_content = hashlib.md5()
        hashed_content.update(text.encode('utf-8'))
        filepath = hashed_content.hexdigest() + " (encoded)"

        # If file has already been encoded, return the encoded file data
        if self.check_downloaded_file(filepath):
            config.LOGGER.info("\tFound encoded file for {}".format(filepath))
            return self.track_existing_file(filepath)

        config.LOGGER.info("\tConverting base64 to file")
        with tempfile.NamedTemporaryFile(suffix=".{}".format(file_formats.PNG)) as tempf:
            tempf.close()
            write_base64_to_file(text, tempf.name)
            return self.download_file(tempf.name, title, preset=preset, extracted=True, original_filepath=filepath)
