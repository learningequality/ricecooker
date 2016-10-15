import os
import requests

PRODUCTION_DOMAIN = "https://contentworkshop.learningequality.org"
DEBUG_DOMAIN = "http://127.0.0.1:8000"

FILE_DIFF_URL = "{domain}/api/internal/file_diff"
FILE_UPLOAD_URL = "{domain}/api/internal/file_upload"
CREATE_CHANNEL_URL = "{domain}/api/internal/create_channel"
OPEN_CHANNEL_URL = "{domain}/open_channel/{invitation_id}/{channel_id}"

STORAGE_DIRECTORY = "storage/"


def get_storage_path(filename):
	return os.path.join(STORAGE_DIRECTORY, filename)

def file_diff_url(domain):
	return FILE_DIFF_URL.format(domain=domain)

def file_upload_url(domain):
	return FILE_UPLOAD_URL.format(domain=domain)

def create_channel_url(domain):
	return CREATE_CHANNEL_URL.format(domain=domain)

def open_channel_url(invitation, channel, domain):
	return OPEN_CHANNEL_URL.format(domain=domain, invitation_id=invitation, channel_id=channel)
