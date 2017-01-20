import os
import sys
import requests
import json
import logging
import webbrowser
from . import config
from .classes import nodes, questions
from requests.exceptions import HTTPError
from requests_file import FileAdapter
from .managers.downloader import DownloadManager
from .managers.progress import RestoreManager, Status
from .managers.tree import ChannelManager
from importlib.machinery import SourceFileLoader

# Fix to support Python 2.x.
# http://stackoverflow.com/questions/954834/how-do-i-use-raw-input-in-python-3
try:
    input = raw_input
except NameError:
    pass

def uploadchannel(path, verbose=False, update=False, resume=False, reset=False, step=Status.LAST.name, token="#", prompt=False, publish=False, warnings=False, compress=False, **kwargs):
    """ uploadchannel: Upload channel to Kolibri Studio server
        Args:
            path (str): path to file containing construct_channel method
            verbose (bool): indicates whether to print process (optional)
            update (bool): indicates whether to re-download files (optional)
            resume (bool): indicates whether to resume last session automatically (optional)
            step (str): step to resume process from (optional)
            reset (bool): indicates whether to start session from beginning automatically (optional)
            token (str): authorization token (optional)
            prompt (bool): indicates whether to prompt user to open channel when done (optional)
            publish (bool): indicates whether to automatically publish channel (optional)
            warnings (bool): indicates whether to print out warnings (optional)
            compress (bool): indicates whether to compress larger files (optional)
            kwargs (dict): keyword arguments to pass to sushi chef (optional)
        Returns: (str) link to access newly created channel
    """

    # Set configuration settings
    level = logging.INFO if verbose else logging.WARNING if warnings else logging.ERROR
    config.LOGGER.addHandler(logging.StreamHandler())
    logging.getLogger("requests").setLevel(logging.WARNING)
    config.LOGGER.setLevel(level)

    # Mount file:// to allow local path requests
    config.SESSION.mount('file://', FileAdapter())
    config.SESSION.headers.update({"Authorization": "Token {0}".format(token)})
    config.UPDATE = update
    config.COMPRESS = compress

    # Get domain to upload to
    config.init_file_mapping_store()
    config.DOWNLOADER = DownloadManager(config.get_file_store())

    # Authenticate user
    if token != "#":
        if os.path.isfile(token):
            with open(token, 'r') as fobj:
                token = fobj.read()
        try:
            response = config.SESSION.post(config.authentication_url())
            response.raise_for_status()
            user = json.loads(response._content.decode("utf-8"))
            config.LOGGER.info("Logged in with username {0}".format(user['username']))

        except HTTPError:
            config.LOGGER.error("Invalid token: Credentials not found")
            sys.exit()
    else:
        prompt_token(config.DOMAIN)

    config.LOGGER.info("\n\n***** Starting channel build process *****\n\n")

    # Set up progress tracker
    config.PROGRESS_MANAGER = RestoreManager()
    if (reset or not config.PROGRESS_MANAGER.check_for_session()) and step.upper() != Status.DONE.name:
        config.PROGRESS_MANAGER.init_session()
    else:
        if resume or prompt_resume():
            config.LOGGER.info("Resuming your last session...")
            step = Status.LAST.name if step is None else step
            config.PROGRESS_MANAGER = config.PROGRESS_MANAGER.load_progress(step.upper())
        else:
            config.PROGRESS_MANAGER.init_session()

    # Construct channel if it hasn't been constructed already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.CONSTRUCT_CHANNEL.value:
        config.PROGRESS_MANAGER.set_channel(run_construct_channel(path, kwargs))
    channel = config.PROGRESS_MANAGER.channel

    # Set initial tree if it hasn't been set already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.CREATE_TREE.value:
        config.PROGRESS_MANAGER.set_tree(create_initial_tree(channel))
    tree = config.PROGRESS_MANAGER.tree

    # Download files if they haven't been downloaded already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.DOWNLOAD_FILES.value:
        config.PROGRESS_MANAGER.set_files(*process_tree_files(tree))

    # Compress files if they haven't been compressed already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.COMPRESS_FILES.value:
        config.PROGRESS_MANAGER.set_compressed_files(*compress_tree_files(tree))

    # Set download manager in case steps were skipped
    config.DOWNLOADER.files = config.PROGRESS_MANAGER.files_downloaded
    config.DOWNLOADER.failed_files = config.PROGRESS_MANAGER.files_failed
    config.DOWNLOADER._file_mapping = config.PROGRESS_MANAGER.file_mapping
    config.set_file_store(config.DOWNLOADER.file_store)

    # Get file diff if it hasn't been generated already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.GET_FILE_DIFF.value:
        config.PROGRESS_MANAGER.set_diff(get_file_diff(tree))
    file_diff = config.PROGRESS_MANAGER.file_diff

    # Set which files have already been uploaded
    tree.uploaded_files = config.PROGRESS_MANAGER.files_uploaded

    # Upload files if they haven't been uploaded already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.UPLOADING_FILES.value:
        config.PROGRESS_MANAGER.set_uploaded(upload_files(tree, file_diff))

    # Create channel on Kolibri Studio if it hasn't been created already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.UPLOAD_CHANNEL.value:
        config.PROGRESS_MANAGER.set_channel_created(*create_tree(tree))
    channel_link = config.PROGRESS_MANAGER.channel_link
    channel_id = config.PROGRESS_MANAGER.channel_id

    # Publish tree if flag is set to True
    if publish and config.PROGRESS_MANAGER.get_status_val() <= Status.PUBLISH_CHANNEL.value:
        publish_tree(tree, channel_id)
        config.PROGRESS_MANAGER.set_published()

    # Open link on web browser (if specified) and return new link
    config.LOGGER.info("\n\nDONE: Channel created at {0}\n".format(channel_link))
    if prompt:
        prompt_open(channel_link)
    config.PROGRESS_MANAGER.set_done()
    return channel_link

def prompt_token(domain):
    """ prompt_token: Prompt user to enter authentication token
        Args: domain (str): domain to authenticate user
        Returns: Authenticated response
    """
    token = input("\nEnter authentication token ('q' to quit):").lower()
    if token == 'q':
        sys.exit()
    else:
        try:
            config.SESSION.headers.update({"Authorization": "Token {0}".format(token)})
            response = config.SESSION.post(config.authentication_url())
            response.raise_for_status()
            return token
        except HTTPError:
            config.LOGGER.error("Invalid token. Please login to {0}/settings/tokens to retrieve your authorization token.".format(domain))
            prompt_token(domain)

def prompt_resume():
    """ prompt_resume: Prompt user to resume last session if one exists
        Args: None
        Returns: None
    """
    openNow = input("\nPrevious session detected. Would you like to resume your previous session? [y/n]:").lower()
    if openNow.startswith("y"):
        return True
    elif openNow.startswith("n"):
        return False
    else:
        return prompt_resume()

def run_construct_channel(path, kwargs):
    """ run_construct_channel: Run sushi chef's construct_channel method
        Args:
            path (str): path to sushi chef file
            kwargs (dict): additional keyword arguments
        Returns: channel created from contruct_channel method
    """
    # Read in file to access create_channel method
    mod = SourceFileLoader("mod", path).load_module()

    # Create channel (using method from imported file)
    config.LOGGER.info("Constructing channel... ")
    channel = mod.construct_channel(**kwargs)
    return channel

def create_initial_tree(channel):
    """ create_initial_tree: Create initial tree structure
        Args:
            channel (Channel): channel to construct
        Returns: tree manager to run rest of steps
    """
    # Create channel manager with channel data
    config.LOGGER.info("   Setting up initial channel structure... ")
    tree = ChannelManager(channel)

    # Make sure channel structure is valid
    config.LOGGER.info("   Validating channel structure...")
    channel.print_tree()
    tree.validate()
    config.LOGGER.info("   Tree is valid\n")
    return tree

def process_tree_files(tree):
    """ process_tree_files: Download files from nodes
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
        Returns: None
    """
    # Fill in values necessary for next steps
    config.LOGGER.info("Processing content...")
    tree.process_tree(tree.channel)
    tree.check_for_files_failed()
    return config.DOWNLOADER.get_files(), config.DOWNLOADER.get_file_mapping(), config.DOWNLOADER.failed_files

def compress_tree_files(tree):
    """ compress_tree_files: Compress files from nodes
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
        Returns: None
    """
    if config.COMPRESS:
        config.LOGGER.info("Compressing files...")
        tree.compress_tree(tree.channel)
        config.set_file_store(config.DOWNLOADER.file_store)
    return config.DOWNLOADER.get_files(), config.DOWNLOADER.get_file_mapping(), config.DOWNLOADER.failed_files

def get_file_diff(tree):
    """ get_file_diff: Download files from nodes
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
        Returns: list of files that are not on Kolibri Studio
    """
    # Determine which files have not yet been uploaded to the CC server
    config.LOGGER.info("Checking if files exist on Kolibri Studio...")
    file_diff = tree.get_file_diff()
    return file_diff

def upload_files(tree, file_diff):
    """ upload_files: Upload files to Kolibri Studio
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            file_diff ([str]): list of files to upload
        Returns: None
    """
    # Upload new files to CC
    tree.upload_files(file_diff)
    tree.reattempt_upload_fails()
    return file_diff

def create_tree(tree):
    """ create_tree: Upload tree to Kolibri Studio
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
        Returns: channel id of created channel and link to channel
    """
    # Create tree
    config.LOGGER.info("Creating tree on Kolibri Studio...")
    channel_id, channel_link = tree.upload_tree()

    return channel_link, channel_id

def prompt_open(channel_link):
    """ prompt_open: Prompt user to open web browser
        Args:
            channel_link (str): url of uploaded channel
        Returns: None
    """
    openNow = input("\nWould you like to open your channel now? [y/n]:").lower()
    if openNow.startswith("y"):
        config.LOGGER.info("Opening channel... ")
        webbrowser.open_new_tab(channel_link)
    elif openNow.startswith("n"):
        return
    else:
        prompt_open(channel_link)

def publish_tree(tree, channel_id):
    """ publish_tree: Publish tree to Kolibri
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            channel_id (str): id of channel to publish
        Returns: None
    """
    config.LOGGER.info("Publishing tree to Kolibri... ")
    tree.publish(channel_id)
