PRODUCTION_DOMAIN = "contentworkshop.learningequality.org"
DEBUG_DOMAIN = "127.0.0.1:8000"

FILE_DIFF_URL = "http://{domain}/api/internal/file_diff"
FILE_UPLOAD_URL = "http://{domain}/api/internal/file_upload"
CREATE_CHANNEL_URL = "http://{domain}/api/internal/create_channel"
OPEN_CHANNEL_URL = "http://{domain}/open_channel/{invitation_id}/{channel_id}"

def file_diff_url(domain):
	return FILE_DIFF_URL.format(domain=domain)

def file_upload_url(domain):
	return FILE_UPLOAD_URL.format(domain=domain)

def create_channel_url(domain):
	return CREATE_CHANNEL_URL.format(domain=domain)

def open_channel_url(invitation, channel, domain):
	return OPEN_CHANNEL_URL.format(domain=domain, invitation_id=invitation, channel_id=channel)
