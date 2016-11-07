# Managers to handle overall structures and api calls

import uuid
import hashlib
import json
import requests
import validators
import base64
import tempfile
import shutil
import pickle
import os
import sys
import filecmp
import requests
from enum import Enum
from requests_file import FileAdapter
from requests.exceptions import MissingSchema, HTTPError, ConnectionError, InvalidURL, InvalidSchema
from io import BytesIO
from PIL import Image
from ricecooker import config
from ricecooker.exceptions import InvalidFormatException, FileNotFoundException
from le_utils.constants import file_formats, exercises, format_presets

WEB_GRAPHIE_URL_REGEX = r'web\+graphie:([^\)]+)'
FILE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'

class DownloadManager:
    """ Manager for handling file downloading and storage

        Attributes:
            session (Session): session to handle requests
            all_file_extensions ([str]): all accepted file extensions
            files ([str]): files that have been downloaded by download manager
            _file_mapping ([{'filename':{...}]): map from filename to file metadata
            verbose (bool): indicates whether to print what manager is doing (optional)
    """

    # All accepted file extensions
    all_file_extensions = [key for key, value in file_formats.choices]

    def __init__(self, file_store, verbose=False, update=False):
        # Mount file:// to allow local path requests
        self.session = requests.Session()
        self.session.mount('file://', FileAdapter())
        self.update = update
        self.file_store = {}
        if os.stat(file_store).st_size > 0:
            with open(file_store, 'r') as jsonobj:
                self.file_store = json.load(jsonobj)
        self.files = []
        self.failed_files = []
        self._file_mapping = {} # Used to keep track of files and their respective metadata
        self.verbose = verbose

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
        print("   The following files could not be accessed:")
        for f in self.failed_files:
            print("\t{id}: {path}".format(id=f[1], path=f[0]))

    def download_graphie(self, path, title):
        """ download_graphie: download a web+graphie file
            Args: path (str): path to .svg and .json files
            Returns: the combined hash of graphie files and their filenames
        """
        try:
            # Handle if path has already been processed
            if exercises.CONTENT_STORAGE_PLACEHOLDER in path:
                filename = os.path.split(path)[-1]
                return filename, filename + ".svg", filename + "-data.json"

            # Initialize paths and hash
            hash = hashlib.md5()
            svg_path = path + ".svg"
            json_path = path + "-data.json"

            # Get svg hash
            try:
                rsvg = self.session.get(svg_path, stream=True)
                rsvg.raise_for_status()
                hash = self.get_hash(rsvg, hash)
            except MissingSchema:
                with open(svg_path, 'rb') as fsvg:
                    hash = self.get_hash(iter(lambda: fsvg.read(4096), b""), hash)

            # Combine svg hash with json hash
            try:
                rjson = self.session.get(json_path, stream=True)
                rjson.raise_for_status()
                hash = self.get_hash(rjson, hash)
            except MissingSchema:
                # Try opening path as relative file path
                with open(json_path, 'rb') as fjson:
                    hash = self.get_hash(iter(lambda: fjson.read(4096), b""), hash)

            # Download files
            svg_result = self.download_file(svg_path, title, hash, default_ext='.{}'.format(file_formats.SVG), preset=format_presets.EXERCISE_GRAPHIE, force_ext=True)
            if not svg_result:
                raise FileNotFoundError("Could not access file: {0}".format(svg_path))
            svg_filename = svg_result

            json_result = self.download_file(json_path, title, hash, default_ext='-data.{}'.format(file_formats.JSON), preset=format_presets.EXERCISE_GRAPHIE, force_ext=True)
            if not json_result:
                raise FileNotFoundError("Could not access file: {0}".format(json_path))
            json_filename = json_result

            return hash.hexdigest(), svg_filename, json_filename
        # Catch errors related to reading file path and handle silently
        except (HTTPError, FileNotFoundError, ConnectionError, InvalidURL, InvalidSchema, IOError):
            self.failed_files += [(path,title)]
            return False;

    def get_hash(self, request, hash_to_update):
        """ get_hash: generate hash of file
            Args:
                request (request): requested file
                hash_to_update (hash): hash to update based on file
            Returns: updated hash
        """
        for chunk in request:
            hash_to_update.update(chunk)
        return hash_to_update

    def download_file(self, path, title, hash=None, default_ext=None, preset=None, force_ext=False):
        """ download_file: downloads file from path
            Args:
                path (str): local path or url to file to download
                hash (hash): hash to use for filename (optional)
                default_ext (str): extension to use if none given (optional)
                preset (str): preset to use (optional)
                force_ext (bool): force manager to use default extension (optional)
            Returns: filename of downloaded file
        """
        try:
            # Handle if path has already been processed
            if exercises.CONTENT_STORAGE_PLACEHOLDER in path:
                return os.path.split(path)[-1]

            if not self.update and path in self.file_store:
                data = self.file_store[path]
                if self.verbose:
                    print("\tFile {0} already exists (add '-u' flag to update)".format(data['filename']))
                self.track_file(data['filename'], data['size'],  data['preset'])
                return data['filename']

            if self.verbose:
                print("\tDownloading {}".format(path))

            # Generate hash if none exist
            if hash is None:
                try:
                    r = self.session.get(path, stream=True)
                    r.raise_for_status()
                    hash = self.get_hash(r, hashlib.md5())
                except MissingSchema:
                    with open(path, 'rb') as fobj:
                        hash = self.get_hash(iter(lambda: fobj.read(4096), b""), hashlib.md5())

            # Get extension of file or default if none found
            file_components = path.split("/")[-1].split(".")
            original_filename = file_components[0]
            extension = file_components[-1].lower()
            if force_ext or extension not in self.all_file_extensions:
                if default_ext is not None:
                    extension = default_ext
                else:
                    raise FileNotFoundError("No extension found: {}".format(path))
            else:
                extension = "." + extension
            filename = '{0}{ext}'.format(hash.hexdigest(), ext=extension)


            # If file already exists, skip it
            if os.path.isfile(config.get_storage_path(filename)):
                if self.verbose:
                    print("\t--- No changes detected on {0}".format(filename))

                # Keep track of downloaded file
                self.track_file(filename, os.path.getsize(config.get_storage_path(filename)), preset, path)
                return filename

            # Write file to temporary file
            with tempfile.TemporaryFile() as tempf:
                try:
                    # Access path
                    r = self.session.get(path, stream=True)
                    r.raise_for_status()

                    # Write to file (generate hash if none provided)
                    for chunk in r:
                        tempf.write(chunk)

                except MissingSchema:
                    # If path is a local file path, try to open the file (generate hash if none provided)
                    with open(path, 'rb') as fobj:
                        tempf.write(fobj.read())

                # Get file metadata (hashed filename, original filename, size)
                file_size = tempf.tell()
                tempf.seek(0)

                # Keep track of downloaded file
                self.track_file(filename, file_size, preset, path)

                # Write file to local storage
                with open(config.get_storage_path(filename), 'wb') as destf:
                    shutil.copyfileobj(tempf, destf)

                if self.verbose:
                    print("\t--- Downloaded '{0}' to {1}".format(original_filename, filename))
            return filename
        # Catch errors related to reading file path and handle silently
        except (HTTPError, FileNotFoundError, ConnectionError, InvalidURL, InvalidSchema, IOError):
            self.failed_files += [(path,title)]
            return False;

    def track_file(self, filename, file_size, preset, path=None):
        self.files += [filename]
        file_data = {filename : {
            'size': file_size,
            'preset':preset,
        }}
        self._file_mapping.update(file_data)

        if path is not None:
            self.file_store.update({path:{
                'filename' : filename,
                'size': file_size,
                'preset':preset,
            }})


    def download_files(self,files, title, default_ext=None):
        """ download_files: download list of files
            Args:
                files ([str]): list of file paths or urls to download
                title (str): name of node in case of error
            Returns: list of downloaded filenames
        """
        file_list = []
        for f in files:
            file_data = f.split('/')[-1]
            result = self.download_file(f, title, default_ext=default_ext)
            if result:
                file_list += [result]
        return file_list

    def encode_thumbnail(self, thumbnail):
        """ encode_thumbnail: gets base64 encoding of thumbnail
            Args:
                thumbnail (str): file path or url to channel's thumbnail
            Returns: base64 encoding of thumbnail
        """
        if thumbnail is None:
            return None
        else:
            # Check if thumbanil path is valid
            if validators.url(thumbnail):
                r = self.session.get(thumbnail, stream=True)
                if r.status_code == 200:
                    # Write thumbnail to temporary file
                    thumbnail = tempfile.TemporaryFile()
                    for chunk in r:
                        thumbnail.write(chunk)

            # Open image and resize accordingly
            img = Image.open(thumbnail)
            width = 200
            height = int((float(img.size[1])*float(width/float(img.size[0]))))
            img.thumbnail((width,height), Image.ANTIALIAS)

            # Write image to bytes for encoding
            bufferstream = BytesIO()
            img.save(bufferstream, format="PNG")
            return "data:image/png;base64," + base64.b64encode(bufferstream.getvalue()).decode('utf-8')

class ChannelManager:
    """ Manager for handling channel tree structure and communicating to server

        Attributes:
            channel (Channel): channel that manager is handling
            domain (str): server domain to create channel on
            downloader (DownloadManager): download manager for handling files
            verbose (bool): indicates whether to print what manager is doing (optional)
    """
    def __init__(self, channel, domain, file_store, verbose=False, update=False):
        self.channel = channel # Channel to process
        self.verbose = verbose # Determines whether to print process
        self.domain = domain # Domain to upload channel to
        self.downloader = DownloadManager(file_store, verbose, update)
        self.uploaded_files=[]

    def validate(self):
        """ validate: checks if tree structure is valid
            Args: None
            Returns: boolean indicating if tree is valid
        """
        return self.channel.test_tree()

    def set_relationship(self, node, parent=None):
        """ set_relationship: sets ids
            Args:
                node (Node): node to process
                parent (Node): parent of node being processed
            Returns: None
        """
        from ricecooker.classes import nodes

        # If node is not a channel, set ids and download files
        if not isinstance(node, nodes.Channel):
            node.set_ids(self.channel._internal_domain, parent.node_id)

        # Process node's children
        for child_node in node.children:
            self.set_relationship(child_node, node)

    def process_tree(self, node, parent=None):
        """ process_tree: processes files
            Args:
                node (Node): node to process
                parent (Node): parent of node being processed
            Returns: None
        """
        from ricecooker.classes import nodes

        # If node is not a channel, download files
        if not isinstance(node, nodes.Channel):
            node.files = self.downloader.download_files(node.files, "Node {}".format(node.original_id))
            if node.thumbnail is not None:
                result = self.downloader.download_files([node.thumbnail], "Node {}".format(node.original_id), default_ext=".{}".format(file_formats.PNG))
                if result:
                    node.files += result

            # If node is an exercise, process images for exercise
            if isinstance(node, nodes.Exercise):
                if self.verbose:
                    print("\t*** Processing images for exercise: {}".format(node.title))
                node.process_questions(self.downloader)

        # Process node's children
        for child_node in node.children:
            self.process_tree(child_node, node)

    def check_for_files_failed(self):
        if self.downloader.has_failed_files():
            self.downloader.print_failed()
        else:
            print("   All files were successfully downloaded")

    def get_file_diff(self, token):
        """ get_file_diff: retrieves list of files that do not exist on content curation server
            Args: None
            Returns: list of files that are not on server
        """
        files_to_diff = self.downloader.get_files()
        file_diff_result = []
        chunks = [files_to_diff[x:x+10000] for x in range(0, len(files_to_diff), 10000)]
        for chunk in chunks:
            response = requests.post(config.file_diff_url(self.domain),  data=json.dumps(chunk))
            response.raise_for_status()
            file_diff_result += json.loads(response._content.decode("utf-8"))
        return file_diff_result

    def upload_files(self, file_list, progress_manager, token):
        """ upload_files: uploads files to server
            Args: file_list (str): list of files to upload
            Returns: None
        """
        counter = 0
        files_to_upload = list(set(file_list) - set(self.uploaded_files)) # In case restoring from previous session
        if self.verbose:
            print("Uploading {0} new file(s) to Kolibri Studio...".format(len(files_to_upload)))
        try:
            for f in files_to_upload:
                with  open(config.get_storage_path(f), 'rb') as file_obj:
                    response = requests.post(config.file_upload_url(self.domain), files={'file': file_obj})
                    response.raise_for_status()
                    self.uploaded_files += [f]
                    counter += 1
                    if self.verbose:
                        print("\tUploaded {0} ({count}/{total}) ".format(f, count=counter, total=len(files_to_upload)))
        finally:
            progress_manager.set_uploading(self.uploaded_files)

    def upload_tree(self, token):
        """ upload_files: sends processed channel data to server to create tree
            Args: None
            Returns: link to uploadedchannel
        """
        payload = {
            "channel_data":self.channel.to_dict(),
            "content_data": [child.to_dict() for child in self.channel.children],
            "file_data": self.downloader._file_mapping,
        }
        response = requests.post(config.create_channel_url(self.domain), data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        return config.open_channel_url(new_channel['new_channel'], self.domain, token)

class Status(Enum):
    INIT = 0
    CONSTRUCT_CHANNEL = 1
    CREATE_TREE = 2
    DOWNLOAD_FILES = 3
    GET_FILE_DIFF = 4
    START_UPLOAD = 5
    UPLOADING_FILES = 6
    UPLOAD_FILES = 7
    UPLOAD_CHANNEL = 8
    DONE = 9
    LAST=10


class RestoreManager:
    """ Manager for handling resuming rice cooking process

        Attributes:
            restore_path (str): path to .pickle file to store progress
    """

    def __init__(self, debug):
        self.debug = debug
        self.channel = None
        self.tree = None # Tree to process
        self.files_downloaded = [] # Determines whether to print process
        self.file_mapping = {} # Domain to upload channel to
        self.files_failed = [] # Download all files if true
        self.file_diff = []
        self.files_uploaded = []
        self.channel_link = None
        self.status = Status.INIT

    def check_for_session(self, status=None):
        status = Status.LAST if status is None else status
        return os.path.isfile(self.get_restore_path(status)) and os.path.getsize(self.get_restore_path(status)) > 0

    def get_restore_path(self, status=None):
        status = self.get_status() if status is None else status
        return config.get_restore_path(status.name.lower(), self.debug)

    def record_progress(self):
        with open(self.get_restore_path(Status.LAST), 'wb') as handle, open(self.get_restore_path(), 'wb') as step_handle:
            pickle.dump(self, handle)
            pickle.dump(self, step_handle)

    def load_progress(self, resume_step):
        resume_step = Status[resume_step]
        progress_path = self.get_restore_path(resume_step)

        # If progress is corrupted, revert to step before
        while not self.check_for_session(resume_step):
            print("Ricecooker has not reached {0} status. Reverting to earlier step...".format(resume_step.name))
            # All files are corrupted, restart process
            if resume_step.value - 1 < 0:
                self.init_session()
                return self
            resume_step = Status(resume_step.value - 1)
            progress_path = self.get_restore_path(resume_step)
        print("Starting from status {0}".format(resume_step.name))

        with open(progress_path, 'rb') as handle:
            manager = pickle.load(handle)
            if isinstance(manager, RestoreManager):
                return manager
            else:
                return self

    def get_status(self):
        return self.status

    def get_status_val(self):
        return self.status.value

    def init_session(self):
        for status in Status:
            path = self.get_restore_path(status)
            if os.path.isfile(path):
                os.remove(path)
        self.record_progress()
        self.status = Status.CONSTRUCT_CHANNEL # Set status to next step
        self.record_progress()

    def set_channel(self, channel):
        self.status = Status.CREATE_TREE # Set status to next step
        self.channel = channel
        self.record_progress()

    def set_tree(self, tree):
        self.status = Status.DOWNLOAD_FILES # Set status to next step
        self.tree = tree
        self.record_progress()

    def set_files(self, files_downloaded, file_mapping, files_failed):
        self.status = Status.GET_FILE_DIFF # Set status to next step
        self.files_downloaded = files_downloaded
        self.file_mapping = file_mapping
        self.files_failed = files_failed
        self.record_progress()

    def set_diff(self, file_diff):
        self.status = Status.START_UPLOAD # Set status to next step
        self.file_diff = file_diff
        self.record_progress()

    def set_uploading(self, files_uploaded):
        self.status = Status.UPLOADING_FILES
        self.files_uploaded = files_uploaded
        self.record_progress()

    def set_uploaded(self, files_uploaded):
        self.status = Status.UPLOAD_FILES
        self.files_uploaded = files_uploaded
        self.record_progress()
        self.status = Status.UPLOAD_CHANNEL # Set status to next step
        self.record_progress()

    def set_channel_created(self, channel_link):
        self.status = Status.DONE
        self.channel_link = channel_link
        self.record_progress()

    def set_done(self):
        self.status = Status.DONE
        self.record_progress()
        os.remove(self.get_restore_path(Status.LAST))
