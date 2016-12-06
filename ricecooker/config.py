# Settings for rice cooker

import os
import json

# Domain for uploading to production server
PRODUCTION_DOMAIN = os.getenv('CONTENTWORKSHOP_URL', "https://contentworkshop.learningequality.org")

# Domain for uploading to local machine
DEBUG_DOMAIN = "http://127.0.0.1:8000"

# URL for authenticating user on Kolibri Studio
AUTHENTICATION_URL = "{domain}/api/internal/authenticate_user_internal"

# URL for getting file diff
FILE_DIFF_URL = "{domain}/api/internal/file_diff"

# URL for uploading files to server
FILE_UPLOAD_URL = "{domain}/api/internal/file_upload"

# URL for creating channel on server
CREATE_CHANNEL_URL = "{domain}/api/internal/create_channel"

# URL to return after channel is created
OPEN_CHANNEL_URL = "{domain}/channels/{channel_id}/edit"

# Folder to store downloaded files
STORAGE_DIRECTORY = "storage/"

# Folder to store progress tracking information
RESTORE_DIRECTORY = "restore/"

def get_storage_path(filename):
    """ get_storage_path: returns path to storage directory for downloading content
        Args: filename (str): Name of file to store
        Returns: string path to file
    """
    # Make storage directory for downloaded files if it doesn't already exist
    if not os.path.exists(STORAGE_DIRECTORY) :
        os.makedirs(STORAGE_DIRECTORY)

    return os.path.join(STORAGE_DIRECTORY, filename)


def authentication_url(domain):
    """ authentication_url: returns url to login to Kolibri Studio
        Args: domain (str): domain to log in
        Returns: string url to authenticate_user_internal endpoint
    """
    return AUTHENTICATION_URL.format(domain=domain)

def init_file_mapping_store(debug):
    path = os.path.join(RESTORE_DIRECTORY, "local" if debug else "production")
    # Make storage directory for restore files if it doesn't already exist
    if not os.path.exists(path):
        os.makedirs(path)

    # Create file mapping json if it doesn't exist
    path = os.path.join(RESTORE_DIRECTORY, "file_restore.json")
    if not os.path.isfile(path):
        open(path, 'a').close()

def get_file_store():
    return os.path.join(RESTORE_DIRECTORY, "file_restore.json")

def set_file_store(file_store):
    with open(get_file_store(), 'w') as storeobj:
        json.dump(file_store, storeobj)

def get_restore_path(filename, debug):
    """ get_restore_path: returns path to directory for restoration points
        Args:
            filename (str): Name of file to store
            debug (bool): Determines how to store restoration points
        Returns: string path to file
    """
    path = os.path.join(RESTORE_DIRECTORY, "local" if debug else "production")
    return os.path.join(path, filename + '.pickle')


def file_diff_url(domain):
    """ file_diff_url: returns url to get file diff
        Args: domain (str): domain to get file diff from
        Returns: string url to file_diff endpoint
    """
    return FILE_DIFF_URL.format(domain=domain)

def file_upload_url(domain):
    """ file_upload_url: returns url to upload files
        Args: domain (str): domain to upload files to
        Returns: string url to file_upload endpoint
    """
    return FILE_UPLOAD_URL.format(domain=domain)

def create_channel_url(domain):
    """ create_channel_url: returns url to create channel
        Args: domain (str): domain to create channel on
        Returns: string url to create_channel endpoint
    """
    return CREATE_CHANNEL_URL.format(domain=domain)

def open_channel_url(channel, domain, token):
    """ open_channel_url: returns url to uploaded channel
        Args:
            invitation (str): invitation id to get editing access
            channel (str): channel id of uploaded channel
            domain (str): server where channel was created
        Returns: string url to open channel
    """
    return OPEN_CHANNEL_URL.format(token=token, domain=domain, channel_id=channel)
