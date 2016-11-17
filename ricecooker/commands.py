import os
import sys
import requests
import json
import webbrowser
from ricecooker import config
from ricecooker.classes import nodes, questions
from requests.exceptions import HTTPError
from ricecooker.managers import ChannelManager, RestoreManager, Status

def uploadchannel(path, debug, verbose=False, update=False, resume=False, reset=False, step=Status.LAST.name, token="#", prompt=False, publish=False, warnings=False, **kwargs):
    """ uploadchannel: Upload channel to Kolibri Studio server
        Args:
            path (str): path to file containing construct_channel method
            debug (bool): determine which domain to upload to
            verbose (bool): indicates whether to print process (optional)
            update (bool): indicates whether to re-download files (optional)
            resume (bool): indicates whether to resume last session automatically (optional)
            step (str): step to resume process from (optional)
            reset (bool): indicates whether to start session from beginning automatically (optional)
            token (str): authorization token (optional)
            prompt (bool): indicates whether to prompt user to open channel when done (optional)
            publish (bool): indicates whether to automatically publish channel (optional)
            warnings (bool): indicates whether to print out warnings (optional)
            kwargs (dict): keyword arguments to pass to sushi chef (optional)
        Returns: (str) link to access newly created channel
    """

    # Set configuration settings
    config.VERBOSE = verbose
    config.WARNING = warnings
    config.TOKEN = token
    config.UPDATE = update
    if debug:
      config.DOMAIN = config.DEBUG_DOMAIN
      config.FILE_STORE_LOCATION = config.DEBUG_FILE_STORE_LOCATION

    # Get domain to upload to
    config.init_file_mapping_store()

    # Authenticate user
    if config.TOKEN != "#":
        if os.path.isfile(config.TOKEN):
            with open(config.TOKEN, 'r') as fobj:
                config.TOKEN = fobj.read()
        try:
            response = requests.post(config.authentication_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)})
            response.raise_for_status()
            user=json.loads(response._content.decode("utf-8"))
            if config.VERBOSE:
                sys.stderr.write("\nLogged in with username {0}".format(user['username']))
        except HTTPError:
            sys.stderr.write("\nInvalid token: Credentials not found")
            sys.exit()
    else:
        config.TOKEN = prompt_token(domain)

    if config.VERBOSE:
        sys.stderr.write("\n\n***** Starting channel build process *****")

    # Set up progress tracker
    progress_manager = RestoreManager()
    if (reset or not progress_manager.check_for_session()) and step.upper() != Status.DONE.name:
        progress_manager.init_session()
    else:
        if resume or prompt_resume():
            if config.VERBOSE:
                sys.stderr.write("\nResuming your last session...")
            step = Status.LAST.name if step is None else step
            progress_manager = progress_manager.load_progress(step.upper())
        else:
            progress_manager.init_session()

    # Construct channel if it hasn't been constructed already
    if progress_manager.get_status_val() <= Status.CONSTRUCT_CHANNEL.value:
        channel = run_construct_channel(path, progress_manager, kwargs)
    else:
        channel = progress_manager.channel

    # Set initial tree if it hasn't been set already
    if progress_manager.get_status_val() <= Status.CREATE_TREE.value:
        tree = create_initial_tree(channel, progress_manager, config.get_file_store())
    else:
        tree = progress_manager.tree

    # Download files if they haven't been downloaded already
    if progress_manager.get_status_val() <= Status.DOWNLOAD_FILES.value:
        process_tree_files(tree, progress_manager)
    else:
        tree.downloader.files = progress_manager.files_downloaded
        tree.downloader.failed_files = progress_manager.files_failed
        tree.downloader._file_mapping = progress_manager.file_mapping

    # Get file diff if it hasn't been generated already
    if progress_manager.get_status_val() <= Status.GET_FILE_DIFF.value:
        file_diff = get_file_diff(tree, progress_manager)
    else:
        file_diff = progress_manager.file_diff

    # Set which files have already been uploaded
    tree.uploaded_files = progress_manager.files_uploaded

    # Upload files if they haven't been uploaded already
    if progress_manager.get_status_val() <= Status.UPLOADING_FILES.value:
        upload_files(tree, file_diff, progress_manager)

    # Create channel on Kolibri Studio if it hasn't been created already
    if progress_manager.get_status_val() <= Status.UPLOAD_CHANNEL.value:
        channel_id, channel_link = create_tree(tree, progress_manager)
    else:
        channel_link = progress_manager.channel_link
        channel_id = progress_manager.channel_id

    # Publish tree if flag is set to True
    if publish and progress_manager.get_status_val() <= Status.PUBLISH_CHANNEL.value:
        publish_tree(tree, progress_manager, channel_id)

    # Open link on web browser (if specified) and return new link
    sys.stderr.write("\n\nDONE: Channel created at {0}\n".format(channel_link))
    if prompt:
        prompt_open(channel_link)
    progress_manager.set_done()
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
            response = requests.post(config.authentication_url(domain), headers={"Authorization": "Token {0}".format(token)})
            response.raise_for_status()
            return token
        except HTTPError:
            sys.stderr.write("\nInvalid token. Please login to {0}/settings/tokens to retrieve your authorization token.".format(domain))
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

def run_construct_channel(path, progress_manager, kwargs):
    """ run_construct_channel: Run sushi chef's construct_channel method
        Args:
            path (str): path to sushi chef file
            progress_manager (RestoreManager): manager to keep track of progress
            kwargs (dict): additional keyword arguments
        Returns: channel created from contruct_channel method
    """
    # Read in file to access create_channel method
    exec(open(path).read(), globals())

    # Create channel (using method from imported file)
    if config.VERBOSE:
        sys.stderr.write("\nConstructing channel... ")
    channel = construct_channel(**kwargs)
    progress_manager.set_channel(channel)
    return channel

def create_initial_tree(channel, progress_manager, file_store):
    """ create_initial_tree: Create initial tree structure
        Args:
            channel (Channel): channel to construct
            progress_manager (RestoreManager): manager to keep track of progress
            file_store (str): path to list of files that have been downloaded
        Returns: tree manager to run rest of steps
    """
    # Create channel manager with channel data
    if config.VERBOSE:
        sys.stderr.write("\n   Setting up initial channel structure... ")
    tree = ChannelManager(channel, file_store)
    if config.VERBOSE:
        sys.stderr.write("DONE")

    # Create channel manager with channel data
    if config.VERBOSE:
        sys.stderr.write("\n   Setting up node relationships... ")
    tree.set_relationship(channel)
    if config.VERBOSE:
        sys.stderr.write("DONE")

    # Make sure channel structure is valid
    if config.VERBOSE:
        sys.stderr.write("\n   Validating channel structure...")
        channel.print_tree()
    tree.validate()
    if config.VERBOSE:
        sys.stderr.write("\n   Tree is valid\n")
    progress_manager.set_tree(tree)
    return tree

def process_tree_files(tree, progress_manager):
    """ process_tree_files: Download files from nodes
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            progress_manager (RestoreManager): manager to keep track of progress
        Returns: None
    """
    # Fill in values necessary for next steps
    if config.VERBOSE:
        sys.stderr.write("\nProcessing content...")
    tree.process_tree(tree.channel)
    tree.check_for_files_failed()
    config.set_file_store(tree.downloader.file_store)
    if config.VERBOSE:
        sys.stderr.write("\n")
    progress_manager.set_files(tree.downloader.get_files(), tree.downloader.get_file_mapping(), tree.downloader.failed_files)

def get_file_diff(tree, progress_manager):
    """ get_file_diff: Download files from nodes
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            progress_manager (RestoreManager): manager to keep track of progress
        Returns: list of files that are not on Kolibri Studio
    """
    # Determine which files have not yet been uploaded to the CC server
    if config.VERBOSE:
        sys.stderr.write("\nChecking if files exist on Kolibri Studio...")
    file_diff = tree.get_file_diff()
    if config.VERBOSE:
        sys.stderr.write("\n")
    progress_manager.set_diff(file_diff)
    return file_diff

def upload_files(tree, file_diff, progress_manager):
    """ upload_files: Upload files to Kolibri Studio
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            file_diff ([str]): list of files to upload
            progress_manager (RestoreManager): manager to keep track of progress
        Returns: None
    """
    # Upload new files to CC
    tree.upload_files(file_diff, progress_manager)
    if config.VERBOSE:
        sys.stderr.write("\n")
    progress_manager.set_uploaded(file_diff)

def create_tree(tree, progress_manager):
    """ create_tree: Upload tree to Kolibri Studio
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            progress_manager (RestoreManager): manager to keep track of progress
        Returns: channel id of created channel and link to channel
    """
    # Create tree
    if config.VERBOSE:
        sys.stderr.write("\nCreating tree on Kolibri Studio...")
    channel_id, channel_link = tree.upload_tree()
    progress_manager.set_channel_created(channel_link, channel_id)
    return channel_id, channel_link

def prompt_open(channel_link):
    """ prompt_open: Prompt user to open web browser
        Args:
            channel_link (str): url of uploaded channel
        Returns: None
    """
    openNow = input("\nWould you like to open your channel now? [y/n]:").lower()
    if openNow.startswith("y"):
        sys.stderr.write("\nOpening channel... ")
        webbrowser.open_new_tab(channel_link)
        if config.VERBOSE:
            sys.stderr.write("DONE")
    elif openNow.startswith("n"):
        return
    else:
        prompt_open(channel_link)

def publish_tree(tree, progress_manager, channel_id):
    """ publish_tree: Publish tree to Kolibri
        Args:
            tree (ChannelManager): manager to handle communication to Kolibri Studio
            progress_manager (RestoreManager): manager to keep track of progress
            channel_id (str): id of channel to publish
        Returns: None
    """
    if config.VERBOSE:
        sys.stderr.write("\nPublishing tree to Kolibri... ")
    tree.publish(channel_id)
    if config.VERBOSE:
        sys.stderr.write("DONE")
    progress_manager.set_published()
