# Settings for rice cooker

import os

# Domain for uploading to production server
PRODUCTION_DOMAIN = "https://contentworkshop.learningequality.org"

# Domain for uploading to local machine
DEBUG_DOMAIN = "http://127.0.0.1:8000"

# URL for getting file diff
FILE_DIFF_URL = "{domain}/api/internal/file_diff"

# URL for uploading files to server
FILE_UPLOAD_URL = "{domain}/api/internal/file_upload"

# URL for creating channel on server
CREATE_CHANNEL_URL = "{domain}/api/internal/create_channel"

# URL to return after channel is created
OPEN_CHANNEL_URL = "{domain}/open_channel/{invitation_id}/{channel_id}"

# Folder to store downloaded files
STORAGE_DIRECTORY = "storage/"

def get_storage_path(filename):
	""" get_storage_path: returns path to storage directory for downloading content
        Args: filename (str): Name of file to store
        Returns: string path to file
    """
	return os.path.join(STORAGE_DIRECTORY, filename)

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

def open_channel_url(invitation, channel, domain):
	""" open_channel_url: returns url to uploaded channel
        Args:
        	invitation (str): invitation id to get editing access
        	channel (str): channel id of uploaded channel
        	domain (str): server where channel was created
        Returns: string url to open channel
    """
	return OPEN_CHANNEL_URL.format(domain=domain, invitation_id=invitation, channel_id=channel)
