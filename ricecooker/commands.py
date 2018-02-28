import json
import logging
import sys

import requests
from requests.exceptions import HTTPError
import webbrowser

from . import config, __version__
from .managers.progress import RestoreManager, Status
from .managers.tree import ChannelManager
from .sushi_bar_client import SushiBarClient

# Fix to support Python 2.x.
# http://stackoverflow.com/questions/954834/how-do-i-use-raw-input-in-python-3
try:
    input = raw_input
except NameError:
    pass

__logging_handler = None


def uploadchannel_wrapper(chef, args, options):
    """
    Call `uploadchannel` with SushiBar monitoring and progress reporting enabled.
    Args:

    """
    try:
        args_and_options = args.copy()
        args_and_options.update(options)
        uploadchannel(chef, **args_and_options)
        config.SUSHI_BAR_CLIENT.report_stage('COMPLETED', 0)
    except Exception as e:
        if config.SUSHI_BAR_CLIENT:
            config.SUSHI_BAR_CLIENT.report_stage('FAILURE', 0)
        config.LOGGER.critical(str(e))
        raise
    finally:
        if config.SUSHI_BAR_CLIENT:
            config.SUSHI_BAR_CLIENT.close()
        config.LOGGER.removeHandler(__logging_handler)


def uploadchannel(chef, update=False, thumbnails=False, download_attempts=3, resume=False, reset=False, step=Status.LAST.name, token="#", prompt=False, publish=False,  debug=False, verbose=True, warn=False, quiet=False, compress=False, stage=False, **kwargs):
    """ uploadchannel: Upload channel to Kolibri Studio server
        Args:
            chef (BaseChef or subclass): class that implements the construct_channel method
            update (bool): indicates whether to re-download files (optional)
            thumbnails (bool): indicates whether to automatically derive thumbnails from content (optional)
            download_attempts (int): number of times to retry downloading files (optional)
            resume (bool): indicates whether to resume last session automatically (optional)
            step (str): step to resume process from (optional)
            reset (bool): indicates whether to start session from beginning automatically (optional)
            token (str): content server authorization token
            prompt (bool): indicates whether to prompt user to open channel when done (optional)
            publish (bool): indicates whether to automatically publish channel (optional)
            debug (bool): indicates whether to print out debugging statements (optional)
            verbose (bool): indicates whether to print out info statements (optional)
            warnings (bool): indicates whether to print out warnings (optional)
            quiet (bool): indicates whether to print out errors (optional)
            compress (bool): indicates whether to compress larger files (optional)
            stage (bool): indicates whether to stage rather than deploy channel (optional)
            kwargs (dict): extra keyword args will be passed to get_channel and construct_channel (optional)
        Returns: (str) link to access newly created channel
    """

    # Set configuration settings
    global __logging_handler

    level = logging.NOTSET
    if debug:
        level = logging.DEBUG
    elif warn:
        level = logging.WARNING
    elif quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.INFO


    __logging_handler = logging.StreamHandler()
    config.LOGGER.addHandler(__logging_handler)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("cachecontrol.controller").setLevel(logging.WARNING)
    logging.getLogger("requests.packages").setLevel(logging.WARNING)
    config.LOGGER.setLevel(level)

    config.UPDATE = update
    config.COMPRESS = compress
    config.THUMBNAILS = thumbnails
    config.STAGE = stage
    config.PUBLISH = publish

    # Set max retries for downloading
    config.DOWNLOAD_SESSION.mount('http://', requests.adapters.HTTPAdapter(max_retries=int(download_attempts)))
    config.DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=int(download_attempts)))

    # Get domain to upload to
    config.init_file_mapping_store()

    # Authenticate user and check current Ricecooker version
    username, token = authenticate_user(token)
    check_version_number()

    # Setup Sushibar client based on channel info in `get_channel`
    config.LOGGER.info("Running get_channel... ")
    channel = chef.get_channel(**kwargs)
    config.SUSHI_BAR_CLIENT = SushiBarClient(channel, username, token, nomonitor=kwargs['nomonitor'])

    config.LOGGER.info("\n\n***** Starting channel build process *****\n\n")

    # Set up progress tracker
    config.PROGRESS_MANAGER = RestoreManager()
    if (reset or not config.PROGRESS_MANAGER.check_for_session()) and step.upper() != Status.DONE.name:
        config.PROGRESS_MANAGER.init_session()
    else:
        if resume or prompt_yes_or_no('Previous session detected. Would you like to resume your last session?'):
            config.LOGGER.info("Resuming your last session...")
            step = Status.LAST.name if step is None else step
            config.PROGRESS_MANAGER = config.PROGRESS_MANAGER.load_progress(step.upper())
        else:
            config.PROGRESS_MANAGER.init_session()

    # Construct channel if it hasn't been constructed already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.CONSTRUCT_CHANNEL.value:
        config.LOGGER.info("Calling construct_channel... ")
        channel = chef.construct_channel(**kwargs)
        config.PROGRESS_MANAGER.set_channel(channel)
    channel = config.PROGRESS_MANAGER.channel

    # Set initial tree if it hasn't been set already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.CREATE_TREE.value:
        config.PROGRESS_MANAGER.set_tree(create_initial_tree(channel))
    tree = config.PROGRESS_MANAGER.tree

    # Download files if they haven't been downloaded already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.DOWNLOAD_FILES.value:
        config.LOGGER.info("Downloading files...")
        config.PROGRESS_MANAGER.set_files(*process_tree_files(tree))

    # Set download manager in case steps were skipped
    files_to_diff = config.PROGRESS_MANAGER.files_downloaded
    config.FAILED_FILES = config.PROGRESS_MANAGER.files_failed

    # Get file diff if it hasn't been generated already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.GET_FILE_DIFF.value:
        config.LOGGER.info("Getting file diff...")
        config.PROGRESS_MANAGER.set_diff(get_file_diff(tree, files_to_diff))
    file_diff = config.PROGRESS_MANAGER.file_diff

    # Set which files have already been uploaded
    tree.uploaded_files = config.PROGRESS_MANAGER.files_uploaded

    # Upload files if they haven't been uploaded already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.UPLOADING_FILES.value:
        config.LOGGER.info("Uploading files...")
        config.PROGRESS_MANAGER.set_uploaded(upload_files(tree, file_diff))

    # Create channel on Kolibri Studio if it hasn't been created already
    if config.PROGRESS_MANAGER.get_status_val() <= Status.UPLOAD_CHANNEL.value:
        config.LOGGER.info("Creating channel...")
        config.PROGRESS_MANAGER.set_channel_created(*create_tree(tree))
    channel_link = config.PROGRESS_MANAGER.channel_link
    channel_id = config.PROGRESS_MANAGER.channel_id

    # Publish tree if flag is set to True
    if config.PUBLISH and config.PROGRESS_MANAGER.get_status_val() <= Status.PUBLISH_CHANNEL.value:
        config.LOGGER.info("Publishing channel...")
        publish_tree(tree, channel_id)
        config.PROGRESS_MANAGER.set_published()

    # Open link on web browser (if specified) and return new link
    config.LOGGER.info("\n\nDONE: Channel created at {0}\n".format(channel_link))
    if prompt and prompt_yes_or_no('Would you like to open your channel now?'):
        config.LOGGER.info("Opening channel... ")
        webbrowser.open_new_tab(channel_link)

    config.PROGRESS_MANAGER.set_done()
    return channel_link

def authenticate_user(token):
    """
    Add the content curation Authorizatino `token` header to `config.SESSION`.
    """
    config.SESSION.headers.update({"Authorization": "Token {0}".format(token)})
    try:
        response = config.SESSION.post(config.authentication_url())
        response.raise_for_status()
        user = json.loads(response._content.decode("utf-8"))
        config.LOGGER.info("Logged in with username {0}".format(user['username']))
        return user['username'], token
    except HTTPError:
        config.LOGGER.error("Invalid token: Credentials not found")
        sys.exit()

def check_version_number():
    response = config.SESSION.post(config.check_version_url(), data=json.dumps({"version": __version__}))
    response.raise_for_status()
    result = json.loads(response._content.decode('utf-8'))

    if  result['status'] == 0:
        config.LOGGER.info(result['message'])
    elif result['status'] == 1:
        config.LOGGER.warning(result['message'])
    elif result['status'] == 2:
        config.LOGGER.error(result['message'])
        if not prompt_yes_or_no("Continue anyways?"):
            sys.exit()
    else:
        config.LOGGER.error(result['message'])
        sys.exit()

def prompt_yes_or_no(message):
    """ prompt_yes_or_no: Prompt user to reply with a y/n response
        Args: None
        Returns: None
    """
    user_input = input("{} [y/n]:".format(message)).lower()
    if user_input.startswith("y"):
        return True
    elif user_input.startswith("n"):
        return False
    else:
        return prompt_yes_or_no(message)


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
    files_to_diff = tree.process_tree(tree.channel)
    config.SUSHI_BAR_CLIENT.report_statistics(files_to_diff, topic_count=tree.channel.get_topic_count())
    tree.check_for_files_failed()
    return files_to_diff, config.FAILED_FILES

def get_file_diff(tree, files_to_diff):
    """ get_file_diff: Download files from nodes
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
        Returns: list of files that are not on Kolibri Studio
    """
    # Determine which files have not yet been uploaded to the CC server
    config.LOGGER.info("\nChecking if files exist on Kolibri Studio...")
    file_diff = tree.get_file_diff(files_to_diff)
    return file_diff

def upload_files(tree, file_diff):
    """ upload_files: Upload files to Kolibri Studio
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            file_diff ([str]): list of files to upload
        Returns: None
    """
    # Upload new files to CC
    config.LOGGER.info("\nUploading {0} new file(s) to Kolibri Studio...".format(len(file_diff)))
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
    config.LOGGER.info("\nCreating tree on Kolibri Studio...")
    channel_id, channel_link = tree.upload_tree()
    # channel_id, channel_link = tree.upload_channel_structure()

    return channel_link, channel_id


def publish_tree(tree, channel_id):
    """ publish_tree: Publish tree to Kolibri
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            channel_id (str): id of channel to publish
        Returns: None
    """
    config.LOGGER.info("\nPublishing tree to Kolibri... ")
    tree.publish(channel_id)
