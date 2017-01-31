# Settings for rice cooker

import os
import json
import logging
import hashlib
import requests
import logging
from requests_file import FileAdapter

UPDATE = False
COMPRESS = False
PROGRESS_MANAGER = None
LOGGER = logging.getLogger()

# Domain and file store location for uploading to production server
DOMAIN = os.getenv('CONTENTWORKSHOP_URL', "https://contentworkshop.learningequality.org")
FILE_STORE_LOCATION =  hashlib.md5(DOMAIN.encode('utf-8')).hexdigest()

# URL for authenticating user on Kolibri Studio
AUTHENTICATION_URL = "{domain}/api/internal/authenticate_user_internal"

# URL for checking compatible version on Kolibri Studio
VERSION_CHECK_URL = "{domain}/api/internal/check_version"

# URL for getting file diff
FILE_DIFF_URL = "{domain}/api/internal/file_diff"

# URL for uploading files to server
FILE_UPLOAD_URL = "{domain}/api/internal/file_upload"

# URL for creating channel on server
CREATE_CHANNEL_URL = "{domain}/api/internal/create_channel"

# URL for adding nodes to channel
ADD_NODES_URL = "{domain}/api/internal/add_nodes"

# URL for making final changes to channel
FINISH_CHANNEL_URL = "{domain}/api/internal/finish_channel"

# URL to return after channel is created
OPEN_CHANNEL_URL = "{domain}/channels/{channel_id}/edit"

# URL for publishing channel
PUBLISH_CHANNEL_URL = "{domain}/api/internal/publish_channel"

# Folder to store downloaded files
STORAGE_DIRECTORY = "storage"

# Folder to store progress tracking information
RESTORE_DIRECTORY = "restore"

# Session for communicating to Kolibri Studio
SESSION = requests.Session()

# Cache for filenames
FILECACHE_DIRECTORY = ".ricecookerfilecache"

FAILED_FILES = []

# Session for downloading files
DOWNLOAD_SESSION = requests.Session()
DOWNLOAD_SESSION.mount('file://', FileAdapter())


def get_storage_path(filename):
    """ get_storage_path: returns path to storage directory for downloading content
        Args: filename (str): Name of file to store
        Returns: string path to file
    """
    directory = os.path.join(STORAGE_DIRECTORY, filename[0], filename[1])
    # Make storage directory for downloaded files if it doesn't already exist
    if not os.path.exists(directory) :
        os.makedirs(directory)

    return os.path.join(directory, filename)

def authentication_url():
    """ authentication_url: returns url to login to Kolibri Studio
        Args: None
        Returns: string url to authenticate_user_internal endpoint
    """
    return AUTHENTICATION_URL.format(domain=DOMAIN)

def init_file_mapping_store():
    """ init_file_mapping_store: creates log to keep track of downloaded files
        Args: None
        Returns: None
    """
    # Make storage directory for restore files if it doesn't already exist
    path = os.path.join(RESTORE_DIRECTORY, FILE_STORE_LOCATION)
    if not os.path.exists(path):
        os.makedirs(path)

def get_restore_path(filename):
    """ get_restore_path: returns path to directory for restoration points
        Args:
            filename (str): Name of file to store
        Returns: string path to file
    """
    path = os.path.join(RESTORE_DIRECTORY, FILE_STORE_LOCATION)
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.join(path, filename + '.pickle')


def check_version_url():
    """ check_version_url: returns url to check ricecooker version
        Args: None
        Returns: string url to check version endpoint
    """
    return VERSION_CHECK_URL.format(domain=DOMAIN)


def file_diff_url():
    """ file_diff_url: returns url to get file diff
        Args: None
        Returns: string url to file_diff endpoint
    """
    return FILE_DIFF_URL.format(domain=DOMAIN)

def file_upload_url():
    """ file_upload_url: returns url to upload files
        Args: None
        Returns: string url to file_upload endpoint
    """
    return FILE_UPLOAD_URL.format(domain=DOMAIN)

def create_channel_url():
    """ create_channel_url: returns url to create channel
        Args: None
        Returns: string url to create_channel endpoint
    """
    return CREATE_CHANNEL_URL.format(domain=DOMAIN)

def add_nodes_url():
    """ add_nodes_url: returns url to add nodes to channel
        Args: None
        Returns: string url to add_nodes endpoint
    """
    return ADD_NODES_URL.format(domain=DOMAIN)

def finish_channel_url():
    """ finish_channel_url: returns url to finish uploading a channel
        Args: None
        Returns: string url to finish_channel endpoint
    """
    return FINISH_CHANNEL_URL.format(domain=DOMAIN)

def open_channel_url(channel):
    """ open_channel_url: returns url to uploaded channel
        Args:
            channel (str): channel id of uploaded channel
        Returns: string url to open channel
    """
    return OPEN_CHANNEL_URL.format(domain=DOMAIN, channel_id=channel)

def publish_channel_url():
    """ open_channel_url: returns url to publish channel
        Args: None
        Returns: string url to publish channel
    """
    return PUBLISH_CHANNEL_URL.format(domain=DOMAIN)
