import os
import webbrowser
from ricecooker.config import STORAGE_DIRECTORY
from ricecooker.classes import nodes, questions
from ricecooker.managers import ChannelManager, RestoreManager, Status



def uploadchannel(path, domain, verbose=False, update=False, resume=False, **kwargs):
    """ uploadchannel: Upload channel to Kolibri Studio server
        Args:
            path (str): path to file containing channel data
            domain (str): domain to upload to
            verbose (bool): indicates whether to print process (optional)
        Returns: (str) link to access newly created channel
    """
    # Set up progress tracker
    progress_manager = RestoreManager("restore.pickle")
    if resume:
        progress_manager = progress_manager.load_progress()
    else:
        progress_manager.record_progress()

    channel = run_construct_channel(path, verbose, progress_manager, kwargs)

    tree = create_initial_tree(channel, domain, verbose, update, progress_manager)

    process_tree_files(tree, verbose, progress_manager)

    file_diff = get_file_diff(tree, verbose, progress_manager)

    upload_files(tree, file_diff, verbose, progress_manager)

    channel_link = create_tree(tree, verbose, progress_manager)

    handle_channel_link(channel_link, progress_manager)


def run_construct_channel(path, verbose, progress_manager, kwargs):
    # Read in file to access create_channel method
    exec(open(path).read(), globals())

    # Create channel (using method from imported file)
    if verbose:
        print("\n\n***** Starting channel build process *****")
        print("Constructing channel...")
    channel = construct_channel(**kwargs)
    progress_manager.set_channel(channel)
    return channel

def create_initial_tree(channel, domain, verbose, update, progress_manager):
    # Make storage directory for downloaded files if it doesn't already exist
    if not os.path.exists(STORAGE_DIRECTORY):
        os.makedirs(STORAGE_DIRECTORY)

    # Create channel manager with channel data
    if verbose:
        print("Setting up initial channel structure...")
    tree = ChannelManager(channel, domain, verbose, update)

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
    progress_manager.set_files(tree.downloader.get_files(), tree.downloader.get_file_mapping(), tree.downloader.failed_files)

def get_file_diff(tree, verbose, progress_manager):
    # Determine which files have not yet been uploaded to the CC server
    if verbose:
        print("Getting file diff...")
    file_diff = tree.get_file_diff()
    progress_manager.set_diff(file_diff)
    return file_diff

def upload_files(tree, file_diff, verbose, progress_manager):
    # Upload new files to CC
    if verbose:
        print("Uploading {0} new file(s) to the content curation server...".format(len(file_diff)))
    tree.upload_files(file_diff)
    progress_manager.set_uploaded(file_diff)

def create_tree(tree, verbose, progress_manager):
    # Create tree
    if verbose:
        print("Creating tree on the content curation server...")
    channel_link = tree.upload_tree()
    progress_manager.set_channel_created(channel_link)
    return channel_link

def handle_channel_link(channel_link, progress_manager):
    # Open link on web browser (if specified) and return new link
    print("DONE: Channel created at {0}".format(channel_link))
    prompt_open(channel_link)
    progress_manager.set_done()

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