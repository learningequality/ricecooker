import os
import webbrowser
from ricecooker.config import STORAGE_DIRECTORY
from ricecooker.classes import nodes, questions
from ricecooker.managers import ChannelManager

def uploadchannel(path, domain, verbose=False, **kwargs):
    """ uploadchannel: Upload channel to Kolibri Studio server
        Args:
            path (str): path to file containing channel data
            domain (str): domain to upload to
            verbose (bool): indicates whether to print process (optional)
        Returns: (str) link to access newly created channel
    """
    # Read in file to access create_channel method
    exec(open(path).read(), globals())

    # Create channel (using method from imported file)
    if verbose:
        print("\n\n***** Starting channel build process *****")
        print("Constructing channel...")
    channel = construct_channel(**kwargs)

    # Make storage directory for downloaded files if it doesn't already exist
    if not os.path.exists(STORAGE_DIRECTORY):
        os.makedirs(STORAGE_DIRECTORY)

    # Create channel manager with channel data
    if verbose:
        channel.print_tree()
        print("Setting up initial channel structure...")
    tree = ChannelManager(channel, domain, verbose)

    # Make sure channel structure is valid
    if verbose:
        print("Validating channel structure...")
    tree.validate()

    # Fill in values necessary for next steps
    if verbose:
        print("Processing content...")
    tree.process_tree(channel)
    tree.check_for_files_failed()

    # Determine which files have not yet been uploaded to the CC server
    if verbose:
        print("Getting file diff...")
    file_diff = tree.get_file_diff()

    # Upload new files to CC
    if verbose:
        print("Uploading {0} new file(s) to the content curation server...".format(len(file_diff)))
    tree.upload_files(file_diff)

    # Create tree
    if verbose:
        print("Creating tree on the content curation server...")
    channel_link = tree.upload_tree()

    # Open link on web browser (if specified) and return new link
    print("DONE: Channel created at {0}".format(channel_link))
    prompt_open(channel_link)
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