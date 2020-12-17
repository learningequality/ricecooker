"""
Settings and global config values for ricecooker.
"""
import atexit
import hashlib
import logging.config
import os
import requests
from requests_file import FileAdapter
import shutil
import socket
import tempfile



UPDATE = False
COMPRESS = False
THUMBNAILS = False
PUBLISH = False
PROGRESS_MANAGER = None
SUSHI_BAR_CLIENT = None
STAGE = False

# When this is set to true, any failure will raise an error and stop the chef.
# This will likely be set to true in a future version of ricecooker, once
# we can ensure all ricecooker internal functions handle non-fatal errors
# properly.
STRICT = False

# Sometimes chef runs will get stuck indefinitely waiting on data from SSL conn,
# so we add a timeout value as suggested in https://stackoverflow.com/a/30771995
socket.setdefaulttimeout(20)


# Logging is configured globally by calling setup_logging() in the chef's `main`
# Use this as `from ricecooker.config import LOGGER` in your suchichef.py code,
# or use the stanard `logging.getLogger(__name__)` to get a namespaced logger.
LOGGER = logging.getLogger()


# Keep error log when setup_logging is called
_ERROR_LOG = None
_MAIN_LOG = None


def setup_logging(level=logging.INFO, main_log=None, error_log=None, add_loggers=None):
    """
    Set up logging, useful to call from your sushi chef main script

    :param level: Minimum default level for all loggers and handlers
    :param main_log: Main log (typically added in chefs.SushiChef)
    :param error_log: Name of file to log (append) errors in
    :param add_loggers: An iterable of other loggers to configure (['scrapy'])
    """
    global _ERROR_LOG, _MAIN_LOG

    if not error_log:
        error_log = _ERROR_LOG
    else:
        _ERROR_LOG = error_log

    if not main_log:
        main_log = _MAIN_LOG
    else:
        _MAIN_LOG = main_log

    # logging dictconfig for handlers
    handlers = {
        "console": {
            "level": level,
            "class": "logging.StreamHandler",
            "formatter": "colored",
        },
    }
    logger_handlers = ["console"]
    if main_log:
        logger_handlers.append("file")
        handlers["file"] = {
            "level": level,
            "class": "logging.FileHandler",
            "filename": main_log,
            "formatter": "simple_date",
        }
    if error_log:
        logger_handlers.append("error")
        handlers["error"] = {
            "level": logging.WARNING,
            "class": "logging.FileHandler",
            "filename": error_log,
            "formatter": "simple_date",
        }

    # The default configuration of a logger (used in below config)
    default_logger_config = {
        "handlers": logger_handlers,
        "propagate": False,
        "level": level,
    }

    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'colored': {
                '()': 'colorlog.ColoredFormatter',
                'format': "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s"
            },
            "simple_date": {
                "format": "%(levelname)-8s %(asctime)s %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handlers,
        "loggers": {
            "": {"handlers": logger_handlers, "level": level},
            "ricecooker": default_logger_config,
        },
    }

    for logger in add_loggers or ():
        config["loggers"][logger] = default_logger_config

    logging.config.dictConfig(config)

    # Silence noisy libraries loggers
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("cachecontrol.controller").setLevel(logging.WARNING)
    logging.getLogger("requests.packages").setLevel(logging.WARNING)
    logging.getLogger("urllib3.util.retry").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connection").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)


# Setup default logging. This is required so we have a basic logging setup until
# prope user-confgured logging is configured in `SushiChef.config_logger`.
setup_logging()


# Domain and file store location for uploading to production Studio server
DEFAULT_DOMAIN = "https://api.studio.learningequality.org"
DOMAIN_ENV = os.getenv('STUDIO_URL', None)
if DOMAIN_ENV is None:  # check old ENV varable for backward compatibility
    DOMAIN_ENV = os.getenv('CONTENTWORKSHOP_URL', None)
DOMAIN = DOMAIN_ENV if DOMAIN_ENV else DEFAULT_DOMAIN
if DOMAIN.endswith('/'):
    DOMAIN = DOMAIN.rstrip('/')
FILE_STORE_LOCATION = hashlib.md5(DOMAIN.encode('utf-8')).hexdigest()

# Allow users to choose which phantomjs they use
PHANTOMJS_PATH = os.getenv('PHANTOMJS_PATH', None)

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

# URL for adding nodes to channel from file
ADD_NODES_FROM_FILE_URL = "{domain}/api/internal/api_add_nodes_from_file"

# URL for making final changes to channel
FINISH_CHANNEL_URL = "{domain}/api/internal/finish_channel"

# URL to return after channel is created
OPEN_CHANNEL_URL = "{domain}/channels/{channel_id}/{access}"

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

# Environment variable indicating we should use a proxy for youtube_dl downloads
USEPROXY = False
USEPROXY = True if os.getenv('USEPROXY') is not None or os.getenv('PROXY_LIST') is not None else False

# CSV headers
CSV_HEADERS = [
    'Source ID',
    'Topic Structure',
    'Old Title',
    'New Title',
    'Old Description',
    'New Description',
    'Old Tags',
    'New Tags',
    'Last Modified'
]

# Automatic temporary direcotry cleanup
chef_temp_dir = os.path.join(os.getcwd(), '.ricecooker-temp')

@atexit.register
def delete_temp_dir():
    if os.path.exists(chef_temp_dir):
        LOGGER.debug("Deleting chef temp files at {}".format(chef_temp_dir))
        shutil.rmtree(chef_temp_dir)

# While in most cases a chef run will clean up after itself, make sure that if it didn't,
# temp files from the old run are deleted so that they do not accumulate.
delete_temp_dir()

# If tempdir is set already, that means the user has explicitly chosen a location for temp storage
if not tempfile.tempdir:
    os.makedirs(chef_temp_dir)
    LOGGER.debug("Setting chef temp dir to {}".format(chef_temp_dir))
    # Store all chef temp files in one dir to avoid issues with temp or even primary storage filling up
    # because of failure by the chef to clean up temp files manually.
    tempfile.tempdir = chef_temp_dir


# Record data about past chef runs in chefdata/ dir
DATA_DIR = 'chefdata'
DATA_FILENAME = 'chef_data.json'
DATA_PATH = os.path.join(DATA_DIR, DATA_FILENAME)
CHEF_DATA_DEFAULT = {
    'current_run': None,
    'runs': [],
    'tree_archives': {
        'previous': None,
        'current': None
    }
}
TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')


# Character limits based on Kolibri models
TRUNCATE_MSG = "\t\t{kind} {id}: {field} {value} is too long - max {max} characters (truncating)"

MAX_TITLE_LENGTH = 200
MAX_SOURCE_ID_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 400
MAX_TAGLINE_LENGTH = 150
MAX_AUTHOR_LENGTH = 200
MAX_AGGREGATOR_LENGTH = 200
MAX_PROVIDER_LENGTH = 200
MAX_SOURCE_URL_LENGTH = 400
MAX_ORIGINAL_FILENAME_LENGTH = 255
MAX_LICENSE_DESCRIPTION_LENGTH = 400
MAX_COPYRIGHT_HOLDER_LENGTH = 200

MAX_CHAR_LIMITS = {
    "title": {
        "kind": "Node",
        "field": "title",
        "max": MAX_TITLE_LENGTH
    },
    "source_id": {
        "kind": "Node",
        "field": "source_id",
        "max": MAX_SOURCE_ID_LENGTH
    },
    "description": {
        "kind": "Node",
        "field": "description",
        "max": MAX_DESCRIPTION_LENGTH
    },
    "tagline": {
        "kind": "Channel",
        "field": "tagline",
        "max": MAX_TAGLINE_LENGTH
    },
    "author": {
        "kind": "Node",
        "field": "author",
        "max": MAX_AUTHOR_LENGTH
    },
    "question_source_url": {
        "kind": "Question",
        "field": "source url",
        "max": MAX_SOURCE_URL_LENGTH
    },
    "original_filename": {
        "kind": "File",
        "field": "original filename",
        "max": MAX_ORIGINAL_FILENAME_LENGTH
    },
    "file_source_url": {
        "kind": "File",
        "field": "source url",
        "max": MAX_SOURCE_URL_LENGTH
    },
    "license_description": {
        "kind": "License",
        "field": "license description",
        "max": MAX_LICENSE_DESCRIPTION_LENGTH
    },
    "copyright_holder": {
        "kind": "License",
        "field": "copyright holder",
        "max": MAX_COPYRIGHT_HOLDER_LENGTH
    },
    "provider": {
        "kind": "Provider",
        "field": "provider",
        "max": MAX_PROVIDER_LENGTH
    },
    "aggregator": {
        "kind": "Aggregator",
        "field": "aggregator",
        "max": MAX_AGGREGATOR_LENGTH
    },
}


def print_truncate(field, id, value, kind=None):
    limit = MAX_CHAR_LIMITS.get(field)
    LOGGER.warning(TRUNCATE_MSG.format(kind=kind or limit["kind"], id=id, field=limit["field"], value=value, max=limit["max"]))

def get_storage_path(filename):
    """ get_storage_path: returns path to storage directory for downloading content
        Args: filename (str): Name of file to store
        Returns: string path to file
    """
    directory = os.path.join(STORAGE_DIRECTORY, filename[0], filename[1])
    # Make storage directory for downloaded files if it doesn't already exist
    if not os.path.exists(directory):
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

def add_nodes_from_file_url():
    """ add_nodes_from_file_url: returns url to add nodes to channel using json file
        Args: None
        Returns: string url to add_nodes endpoint
    """
    return ADD_NODES_FROM_FILE_URL.format(domain=DOMAIN)

def finish_channel_url():
    """ finish_channel_url: returns url to finish uploading a channel
        Args: None
        Returns: string url to finish_channel endpoint
    """
    return FINISH_CHANNEL_URL.format(domain=DOMAIN)

def open_channel_url(channel, staging=False):
    """ open_channel_url: returns url to uploaded channel
        Args:
            channel (str): channel id of uploaded channel
        Returns: string url to open channel
    """
    frontend_domain = DOMAIN.replace("api.", "")  # Don't send them to the API domain for preview / review.
    return OPEN_CHANNEL_URL.format(domain=frontend_domain, channel_id=channel, access='staging' if staging or STAGE else 'edit')

def publish_channel_url():
    """ open_channel_url: returns url to publish channel
        Args: None
        Returns: string url to publish channel
    """
    return PUBLISH_CHANNEL_URL.format(domain=DOMAIN)
