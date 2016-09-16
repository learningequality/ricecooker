from fle_utils import constants
from ricecooker.classes import *
from ricecooker.managers import ChannelManager

def uploadchannel(path, verbose=False):
    exec(open(path).read(), globals())

    if verbose:
        print("\n\n***** Starting channel build process *****")
        print("Constructing channel...")
    channel = construct_channel({})

    if verbose:
        print("Setting up initial channel structure...")
    tree = ChannelManager(channel, verbose)

    if verbose:
        print("Processing content...")
    tree.process_tree(channel)

    if verbose:
        print("Getting file diff...")
    file_diff = tree.get_file_diff()

    if verbose:
        print("Uploading {0} file(s) to the content curation server...".format(len(file_diff)))
    tree.upload_files(file_diff)

    if verbose:
        print("Creating tree on the content curation server...")
    channel_link = tree.upload_tree()
    print("DONE: Channel created at {0}".format(channel_link))
    return channel