import os
import sys
import requests
import json
import webbrowser
from ricecooker import config
from ricecooker.classes import nodes, questions
from requests.exceptions import HTTPError
from ricecooker.managers import ChannelManager, RestoreManager, Status

def uploadchannel(path, debug, verbose=False, update=False, resume=False, reset=False, step=Status.LAST.name, token="#", **kwargs):

    """ uploadchannel: Upload channel to Kolibri Studio server
        Args:
            path (str): path to file containing channel data
            debug (bool): determine which domain to upload to
            verbose (bool): indicates whether to print process (optional)
        Returns: (str) link to access newly created channel
    """
    # Get domain to upload to
    domain = config.PRODUCTION_DOMAIN
    if debug:
        domain = config.DEBUG_DOMAIN
    config.init_file_mapping_store(debug)

    if verbose:
        print("\n\n***** Starting channel build process *****")

    # Set up progress tracker
    progress_manager = RestoreManager(debug)
    if (reset or not progress_manager.check_for_session()) and step.upper() != Status.DONE.name:
        progress_manager.init_session()
    else:
        if resume or prompt_resume():
            if verbose:
                print("Resuming your last session...")
            step = Status.LAST.name if step is None else step
            progress_manager = progress_manager.load_progress(step.upper())
        else:
            progress_manager.init_session()

    # Construct channel if it hasn't been constructed already
    if progress_manager.get_status_val() <= Status.CONSTRUCT_CHANNEL.value:
        channel = run_construct_channel(path, verbose, progress_manager, kwargs)
    else:
        channel = progress_manager.channel

    # Set initial tree if it hasn't been set already
    if progress_manager.get_status_val() <= Status.CREATE_TREE.value:
        tree = create_initial_tree(channel, domain, verbose, update, progress_manager, config.get_file_store())
    else:
        tree = progress_manager.tree

    # Download files if they haven't been downloaded already
    if progress_manager.get_status_val() <= Status.DOWNLOAD_FILES.value:
        process_tree_files(tree, verbose, progress_manager)
    else:
        tree.downloader.files = progress_manager.files_downloaded
        tree.downloader.failed_files = progress_manager.files_failed
        tree.downloader._file_mapping = progress_manager.file_mapping

    # Get file diff if it hasn't been generated already
    if progress_manager.get_status_val() <= Status.GET_FILE_DIFF.value:
        file_diff = get_file_diff(tree, verbose, progress_manager, token)
    else:
        file_diff = progress_manager.file_diff

    # Set which files have already been uploaded
    tree.uploaded_files = progress_manager.files_uploaded

    # Upload files if they haven't been uploaded already
    if progress_manager.get_status_val() <= Status.UPLOADING_FILES.value:
        upload_files(tree, file_diff, verbose, progress_manager, token)

    # Create channel on Kolibri Studio if it hasn't been created already
    if progress_manager.get_status_val() <= Status.UPLOAD_CHANNEL.value:
        channel_link = create_tree(tree, verbose, progress_manager, token)
    else:
        channel_link = progress_manager.channel_link

    # Open link on web browser (if specified) and return new link
    print("DONE: Channel created at {0}".format(channel_link))
    prompt_open(channel_link)
    progress_manager.set_done()
    return channel_link

def prompt_token(domain):
    token = input("Enter authentication token ('q' to quit):").lower()
    if token == 'q':
        sys.exit()
    else:
        try:
            response = requests.post(config.authentication_url(domain), headers={"Authorization": "Token {0}".format(token)})
            response.raise_for_status()
            return response
        except HTTPError:
            print("Invalid token. Please login to {0}/settings/tokens to retrieve your authorization token.".format(domain))
            prompt_token(domain)

def prompt_resume():
    """ prompt_resume: Prompt user to resume last session if one exists
        Args: None
        Returns: None
    """
    openNow = input("Previous session detected. Would you like to resume your previous session? [y/n]:").lower()
    if openNow.startswith("y"):
        return True
    elif openNow.startswith("n"):
        return False
    else:
        return prompt_resume()

def run_construct_channel(path, verbose, progress_manager, kwargs):
    # Read in file to access create_channel method
    exec(open(path).read(), globals())

    # Create channel (using method from imported file)
    if verbose:
        print("Constructing channel...")
    channel = construct_channel(**kwargs)
    progress_manager.set_channel(channel)
    return channel

def create_initial_tree(channel, domain, verbose, update, progress_manager, file_store):

    # Create channel manager with channel data
    if verbose:
        print("Setting up initial channel structure...")
    tree = ChannelManager(channel, domain, file_store, verbose, update)

    # Create channel manager with channel data
    if verbose:
        print("Setting up node relationships..")
    tree.set_relationship(channel)

    # Make sure channel structure is valid
    if verbose:
        print("Validating channel structure...")
        channel.print_tree()
    tree.validate()
    progress_manager.set_tree(tree)
    return tree

def process_tree_files(tree, verbose, progress_manager):
    # Fill in values necessary for next steps
    if verbose:
        print("Processing content...")
    tree.process_tree(tree.channel)
    tree.check_for_files_failed()
    config.set_file_store(tree.downloader.file_store)
    progress_manager.set_files(tree.downloader.get_files(), tree.downloader.get_file_mapping(), tree.downloader.failed_files)

def get_file_diff(tree, verbose, progress_manager, token):
    # Determine which files have not yet been uploaded to the CC server
    if verbose:
        print("Checking if files exist on Kolibri Studio...")
    file_diff = tree.get_file_diff(token)
    progress_manager.set_diff(file_diff)
    return file_diff

def upload_files(tree, file_diff, verbose, progress_manager, token):
    # Upload new files to CC
    tree.upload_files(file_diff, progress_manager, token)
    progress_manager.set_uploaded(file_diff)

def create_tree(tree, verbose, progress_manager, token):
    # Create tree
    if verbose:
        print("Creating tree on Kolibri Studio...")
    channel_link = tree.upload_tree(token)
    progress_manager.set_channel_created(channel_link)
    return channel_link

def prompt_open(channel_link):
    """ prompt_open: Prompt user to open web browser
        Args:
            channel_link (str): url of uploaded channel
        Returns: None
    """
    openNow = input("Would you like to open your channel now? [y/n]:").lower()
    if openNow.startswith("y"):
        print("Opening channel...")
        webbrowser.open_new_tab(channel_link)
    elif openNow.startswith("n"):
        return
    else:
        prompt_open(channel_link)