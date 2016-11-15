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

# Regex to parse for web+graphie prefix
WEB_GRAPHIE_URL_REGEX = r'web\+graphie:([^\)]+)'

# Regex to extract image paths
FILE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'

class DownloadManager:
    """ Manager for handling file downloading and storage

        Attributes:
            session (Session): session to handle requests
            all_file_extensions ([str]): all accepted file extensions
            files ([str]): files that have been downloaded by download manager
            _file_mapping ([{'filename':{...}]): map from filename to file metadata
            verbose (bool): indicates whether to print what manager is doing (optional)
            update (bool): indicates whether to read from file paths again
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
                if self.verbose:
                    print("\tDownloading graphie {}".format(original_filename))

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
                    if self.verbose:
                        print("\t--- No changes detected on {0}".format(filename))
                    # Keep track of downloaded file
                    self.track_file(filename, file_size, format_presets.EXERCISE_GRAPHIE, path_name, original_filename)
                    return self._file_mapping[filename]

                # Write file to local storage
                with open(config.get_storage_path(filename), 'wb') as destf:
                    shutil.copyfileobj(tempf, destf)

                # Keep track of downloaded file
                self.track_file(filename, file_size, format_presets.EXERCISE_GRAPHIE, path_name, original_filename)
                if self.verbose:
                    print("\t--- Downloaded {}".format(filename))
                return self._file_mapping[filename]

        # Catch errors related to reading file path and handle silently
        except (HTTPError, FileNotFoundError, ConnectionError, InvalidURL, InvalidSchema, IOError):
            self.failed_files += [(path,title)]
            return False;

    def write_to_graphie_file(self, path, tempf, hash):
        """ write_to_graphie_file: write from path to graphie file
            Args:
                path (str): path to file to read from
                tempf (TemporaryFile): file to write to
                hash (md5): hash to update during write process
            Returns: None
        """
        try:
            r = self.session.get(path, stream=True)
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
            r = self.session.get(path, stream=True)
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
        return not self.update and path in self.file_store

    def track_existing_file(self, path):
        """ track_existing_file: add file to mapping if already downloaded
            Args:
                path (str): url or path to file to track
            Returns: file data for tracked file
        """
        data = self.file_store[path]
        if self.verbose:
            print("\tFile {0} already exists (add '-u' flag to update)".format(data['filename']))
        self.track_file(data['filename'], data['size'],  data['preset'], original_filename=data['original_filename'])
        return self._file_mapping[data['filename']]

    def download_file(self, path, title, default_ext=None, preset=None):
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

            if self.check_downloaded_file(path):
                return self.track_existing_file(path)

            if self.verbose:
                print("\tDownloading {}".format(path))

            hash=self.get_hash(path)

            # Get extension of file or default if none found
            extension = os.path.splitext(path)[1][1:].lower()
            if extension not in self.all_file_extensions:
                if default_ext is not None:
                    extension = default_ext
                else:
                    raise FileNotFoundError("No extension found: {}".format(path))

            filename = '{0}.{ext}'.format(hash.hexdigest(), ext=extension)

            # If file already exists, skip it
            if os.path.isfile(config.get_storage_path(filename)):
                if self.verbose:
                    print("\t--- No changes detected on {0}".format(filename))

                # Keep track of downloaded file
                self.track_file(filename, os.path.getsize(config.get_storage_path(filename)), preset, path)
                return self._file_mapping[filename]

            # Write file to temporary file
            with tempfile.TemporaryFile() as tempf:
                try:
                    # Access path
                    r = self.session.get(path, stream=True)
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

                # Keep track of downloaded file
                self.track_file(filename, file_size, preset, path)
                if self.verbose:
                    print("\t--- Downloaded {}".format(filename))
                return self._file_mapping[filename]

        # Catch errors related to reading file path and handle silently
        except (HTTPError, FileNotFoundError, ConnectionError, InvalidURL, InvalidSchema, IOError):
            self.failed_files += [(path,title)]
            return False;

    def track_file(self, filename, file_size, preset, path=None, original_filename='[File]'):
        """ track_file: record which file has been downloaded along with metadata
            Args:
                filename (str): name of file to track
                file_size (int): size of file
                preset (str): preset to assign to file
                path (str): source path of file (optional)
                original_filename (str): file's original name (optional)
            Returns: None
        """
        self.files += [filename]
        file_data = {
            'size' : file_size,
            'preset' : preset,
            'filename' : filename,
            'original_filename' : original_filename,
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
        self.update = update # Download all files if true

        self.downloader = DownloadManager(file_store, verbose, update)
        self.uploaded_files=[]
        self.failed_node_builds=[]

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
        if isinstance(node, nodes.Channel):
            if node.thumbnail is not None and node.thumbnail != "":
                file_data = self.downloader.download_file(node.thumbnail, "Channel Thumbnail", default_ext=file_formats.PNG)
                node.thumbnail = file_data['filename'] if file_data else ""
        else:
            node.files = self.downloader.download_files(node.files, "Node {}".format(node.original_id))
            if node.thumbnail is not None:
                result = self.downloader.download_files([node.thumbnail], "Node {}".format(node.original_id), default_ext=file_formats.PNG)
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
        """ check_for_files_failed: print any files that failed during download process
            Args: None
            Returns: None
        """
        if self.downloader.has_failed_files():
            self.downloader.print_failed()
        else:
            print("   All files were successfully downloaded")

    def get_file_diff(self, token):
        """ get_file_diff: retrieves list of files that do not exist on content curation server
            Args: token (str): authentication token
            Returns: list of files that are not on server
        """
        files_to_diff = self.downloader.get_files()
        file_diff_result = []
        chunks = [files_to_diff[x:x+1000] for x in range(0, len(files_to_diff), 1000)]
        file_count = 0
        total_count = len(files_to_diff)
        for chunk in chunks:
            response = requests.post(config.file_diff_url(self.domain), headers={"Authorization": "Token {0}".format(token)}, data=json.dumps(chunk))
            response.raise_for_status()
            file_diff_result += json.loads(response._content.decode("utf-8"))
            file_count += len(chunk)
            if self.verbose:
                print("\tGot file diff for {0} out of {1} files".format(file_count, total_count))

        return file_diff_result

    def upload_files(self, file_list, progress_manager, token):
        """ upload_files: uploads files to server
            Args:
                file_list (str): list of files to upload
                progress_manager (RestoreManager): manager to keep track of progress
                token (str): authentication token
            Returns: None
        """
        counter = 0
        files_to_upload = list(set(file_list) - set(self.uploaded_files)) # In case restoring from previous session
        if self.verbose:
            print("Uploading {0} new file(s) to Kolibri Studio...".format(len(files_to_upload)))
        try:
            for f in files_to_upload:
                with  open(config.get_storage_path(f), 'rb') as file_obj:
                    response = requests.post(config.file_upload_url(self.domain), headers={"Authorization": "Token {0}".format(token)},  files={'file': file_obj})
                    response.raise_for_status()
                    self.uploaded_files += [f]
                    counter += 1
                    if self.verbose:
                        print("\tUploaded {0} ({count}/{total}) ".format(f, count=counter, total=len(files_to_upload)))
        finally:
            progress_manager.set_uploading(self.uploaded_files)

    def upload_tree(self, token):
        """ upload_files: sends processed channel data to server to create tree
            Args: token (str): authentication token
            Returns: link to uploadedchannel
        """
        root, channel_id = self.add_channel(token)
        self.add_nodes(root, self.channel, token)
        if self.check_failed():
            self.failed_node_builds = []
            self.reattempt_failed(token)
            self.check_failed()
        channel_id, channel_link = self.commit_channel(channel_id, token)
        return channel_id, channel_link

    def reattempt_failed(self, token):
        for node in self.failed_node_builds:
            if self.verbose:
                print("Reattempting {0}".format(str(node[1])))
            for f in node[1].files:
                # Attempt to upload file
                with  open(config.get_storage_path(f['filename']), 'rb') as file_obj:
                    response = requests.post(config.file_upload_url(self.domain), headers={"Authorization": "Token {0}".format(token)},  files={'file': file_obj})
                    response.raise_for_status()
                    self.uploaded_files += [f['filename']]
            # Attempt to create node
            self.add_nodes(node[0], node[1], token)

    def check_failed(self):
        if len(self.failed_node_builds) > 0:
            print("The following nodes could not be created:")
            for node in self.failed_node_builds:
                print("\t{}".format(str(node[1])))
            return True
        elif self.verbose:
            print("All nodes were created successfully.")
        return False

    def add_channel(self, token):
        """ add_channel: sends processed channel data to server to create tree
            Args: token (str): authentication token
            Returns: link to uploadedchannel
        """
        if self.verbose:
            print("   Creating channel {0}".format(self.channel.title))
        payload = {
            "channel_data":self.channel.to_dict(),
        }
        response = requests.post(config.create_channel_url(self.domain), headers={"Authorization": "Token {0}".format(token)}, data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))

        return new_channel['root'], new_channel['channel_id']

    def add_nodes(self, root_id, current_node, token, indent=1):
        """ add_nodes: adds processed nodes to tree
            Args:
                root_id (str): id of parent node on Kolibri Studio
                current_node (Node): node to publish children
                token (str): authentication token
                indent (int): level of indentation for printing
            Returns: link to uploadedchannel
        """
        if self.verbose:
            print("{indent}Processing {data}".format(indent="   " * indent, data=str(current_node)))
        payload = {
            'root_id': root_id,
            'content_data': [child.to_dict() for child in current_node.children]
        }
        response = requests.post(config.add_nodes_url(self.domain), headers={"Authorization": "Token {0}".format(token)}, data=json.dumps(payload))
        if response.status_code != 200:
            self.failed_node_builds += [(root_id, current_node)]
        else:
            response_json = json.loads(response._content.decode("utf-8"))

            for child in current_node.children:
                self.add_nodes(response_json['root_ids'][child.node_id.hex], child, token, indent + 1)

    def commit_channel(self, channel_id, token):
        """ commit_channel: commits channel to Kolibri Studio
            Args:
                channel_id (str): channel's id on Kolibri Studio
                token (str): authentication token
            Returns: channel id and link to uploadedchannel
        """
        payload = {
            "channel_id":channel_id,
        }
        response = requests.post(config.finish_channel_url(self.domain), headers={"Authorization": "Token {0}".format(token)}, data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        channel_link = config.open_channel_url(new_channel['new_channel'], self.domain)
        return channel_id, channel_link

    def publish(self, channel_id, token):
        """ publish: publishes tree to Kolibri
            Args:
                channel_id (str): channel's id on Kolibri Studio
                token (str): authentication token
            Returns: None
        """
        payload = {
            "channel_id":channel_id,
        }
        response = requests.post(config.publish_channel_url(self.domain), headers={"Authorization": "Token {0}".format(token)}, data=json.dumps(payload))
        response.raise_for_status()


class Status(Enum):
    """ Enum containing all statuses Ricecooker can have

        Steps:
            INIT: Ricecooker process has been started
            CONSTRUCT_CHANNEL: Ricecooker is ready to call sushi chef's construct_channel method
            CREATE_TREE: Ricecooker is ready to create relationships between nodes
            DOWNLOAD_FILES: Ricecooker is ready to start downloading files
            GET_FILE_DIFF: Ricecooker is ready to get file diff from Kolibri Studio
            START_UPLOAD: Ricecooker is ready to start uploading files to Kolibri Studio
            UPLOADING_FILES: Ricecooker is in the middle of uploading files
            UPLOAD_CHANNEL: Ricecooker is ready to upload the channel to Kolibri Studio
            PUBLISH_CHANNEL: Ricecooker is ready to publish the channel to Kolibri
            DONE: Ricecooker is done
            LAST: Place where Ricecooker left off
    """
    INIT = 0
    CONSTRUCT_CHANNEL = 1
    CREATE_TREE = 2
    DOWNLOAD_FILES = 3
    GET_FILE_DIFF = 4
    START_UPLOAD = 5
    UPLOADING_FILES = 6
    UPLOAD_CHANNEL = 7
    PUBLISH_CHANNEL = 8
    DONE = 9
    LAST = 10


class RestoreManager:
    """ Manager for handling resuming rice cooking process

        Attributes:
            restore_path (str): path to .pickle file to store progress
            debug (bool): determines which server is having progress tracked
            channel (Channel): channel Ricecooker is creating
            tree (ChannelManager): manager Ricecooker is using
            files_downloaded ([str]): list of files that have been downloaded
            file_mapping ({filename:...}): filenames mapped to metadata
            files_failed ([str]): list of files that failed to download
            file_diff ([str]): list of files that don't exist on Kolibri Studio
            files_uploaded ([str]): list of files that have been successfully uploaded
            channel_link (str): link to uploaded channel
            channel_id (str): id of channel that has been uploaded
            status (str): status of Ricecooker
    """

    def __init__(self, debug):
        self.debug = debug
        self.channel = None
        self.tree = None
        self.files_downloaded = []
        self.file_mapping = {}
        self.files_failed = []
        self.file_diff = []
        self.files_uploaded = []
        self.channel_link = None
        self.channel_id = None
        self.status = Status.INIT

    def check_for_session(self, status=None):
        """ check_for_session: see if session is in progress
            Args:
                status (str): step to check if last session reached (optional)
            Returns: boolean indicating if session exists
        """
        status = Status.LAST if status is None else status
        return os.path.isfile(self.get_restore_path(status)) and os.path.getsize(self.get_restore_path(status)) > 0

    def get_restore_path(self, status=None):
        """ get_restore_path: get path to restoration file
            Args:
                status (str): step to get restore file (optional)
            Returns: string path to restoration file
        """
        status = self.get_status() if status is None else status
        return config.get_restore_path(status.name.lower(), self.debug)

    def record_progress(self):
        """ record_progress: save progress to respective restoration file
            Args: None
            Returns: None
        """
        with open(self.get_restore_path(Status.LAST), 'wb') as handle, open(self.get_restore_path(), 'wb') as step_handle:
            pickle.dump(self, handle)
            pickle.dump(self, step_handle)

    def load_progress(self, resume_step):
        """ load_progress: loads progress from restoration file
            Args: resume_step (str): step at which to resume session
            Returns: manager with progress from step
        """
        resume_step = Status[resume_step]
        progress_path = self.get_restore_path(resume_step)

        # If progress is corrupted, revert to step before
        while not self.check_for_session(resume_step):
            print("Ricecooker has not reached {0} status. Reverting to earlier step...".format(resume_step.name))
            # All files are corrupted or absent, restart process
            if resume_step.value - 1 < 0:
                self.init_session()
                return self
            resume_step = Status(resume_step.value - 1)
            progress_path = self.get_restore_path(resume_step)
        print("Starting from status {0}".format(resume_step.name))

        # Load manager
        with open(progress_path, 'rb') as handle:
            manager = pickle.load(handle)
            if isinstance(manager, RestoreManager):
                return manager
            else:
                return self

    def get_status(self):
        """ get_status: retrieves current status of Ricecooker
            Args: None
            Returns: string status of Ricecooker
        """
        return self.status

    def get_status_val(self):
        """ get_status_val: retrieves value of status of Ricecooker
            Args: None
            Returns: number value of status of Ricecooker
        """
        return self.status.value

    def init_session(self):
        """ init_session: sets session to beginning status
            Args: None
            Returns: None
        """
        # Clear out previous session's restoration files
        for status in Status:
            path = self.get_restore_path(status)
            if os.path.isfile(path):
                os.remove(path)

        self.record_progress()
        self.status = Status.CONSTRUCT_CHANNEL # Set status to next step
        self.record_progress()

    def set_channel(self, channel):
        """ set_channel: records progress from constructed channel
            Args: channel (Channel): channel Ricecooker is creating
            Returns: None
        """
        self.status = Status.CREATE_TREE # Set status to next step
        self.channel = channel
        self.record_progress()

    def set_tree(self, tree):
        """ set_channel: records progress from creating the tree
            Args: tree (ChannelManager): manager Ricecooker is using
            Returns: None
        """
        self.status = Status.DOWNLOAD_FILES # Set status to next step
        self.tree = tree
        self.record_progress()

    def set_files(self, files_downloaded, file_mapping, files_failed):
        """ set_files: records progress from downloading files
            Args:
                files_downloaded ([str]): list of files that have been downloaded
                file_mapping ({filename:...}): filenames mapped to metadata
                files_failed ([str]): list of files that failed to download
            Returns: None
        """
        self.status = Status.GET_FILE_DIFF # Set status to next step
        self.files_downloaded = files_downloaded
        self.file_mapping = file_mapping
        self.files_failed = files_failed
        self.record_progress()

    def set_diff(self, file_diff):
        """ set_diff: records progress from getting file diff
            Args: file_diff ([str]): list of files that don't exist on Kolibri Studio
            Returns: None
        """
        self.status = Status.START_UPLOAD # Set status to next step
        self.file_diff = file_diff
        self.record_progress()

    def set_uploading(self, files_uploaded):
        """ set_uploading: records progress during uploading files
            Args: files_uploaded ([str]): list of files that have been successfully uploaded
            Returns: None
        """
        self.status = Status.UPLOADING_FILES
        self.files_uploaded = files_uploaded
        self.record_progress()

    def set_uploaded(self, files_uploaded):
        """ set_uploaded: records progress after uploading files
            Args: files_uploaded ([str]): list of files that have been successfully uploaded
            Returns: None
        """
        self.files_uploaded = files_uploaded
        self.status = Status.UPLOAD_CHANNEL # Set status to next step
        self.record_progress()

    def set_channel_created(self, channel_link, channel_id):
        """ set_channel_created: records progress after creating channel on Kolibri Studio
            Args:
                channel_link (str): link to uploaded channel
                channel_id (str): id of channel that has been uploaded
            Returns: None
        """
        self.status = Status.PUBLISH_CHANNEL
        self.channel_link = channel_link
        self.channel_id = channel_id
        self.record_progress()

    def set_published(self):
        """ set_published: records progress after channel has been published
            Args: None
            Returns: None
        """
        self.status = Status.DONE
        self.record_progress()

    def set_done(self):
        """ set_done: records progress after Ricecooker process has been completed
            Args: None
            Returns: None
        """
        self.status = Status.DONE
        self.record_progress()

        # Delete restoration point for last step to indicate process has been completed
        os.remove(self.get_restore_path(Status.LAST))
