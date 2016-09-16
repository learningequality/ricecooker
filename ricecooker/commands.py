from fle_utils import constants
from ricecooker.classes import *
from ricecooker.managers import ChannelManager

""" uploadchannel: command to create tree on content curation server
    @param path (string path to file containing channel data)
    @param verbose (boolean to determine whether to print process)
    @return link to access newly created channel
"""
def uploadchannel(path, verbose=False):
    exec(open(path).read(), globals())

    if verbose:
        print("\n\n***** Starting channel build process *****")
        print("Constructing channel...")
    channel = construct_channel({}) # Create channel (using method from imported file)

    if verbose:
        print("Setting up initial channel structure...")
    tree = ChannelManager(channel, verbose) # Create channel manager with channel data

    if verbose:
        print("Processing content...")
    tree.process_tree(channel) # Fill in values necessary for next steps

    if verbose:
        print("Getting file diff...")
    file_diff = tree.get_file_diff() # Determine which files have not yet been uploaded to the CC server

    if verbose:
        print("Uploading {0} new file(s) to the content curation server...".format(len(file_diff)))
    tree.upload_files(file_diff) # Upload new files to CC

    if verbose:
        print("Creating tree on the content curation server...")
    channel_link = tree.upload_tree() # Create tree

    print("DONE: Channel created at {0}".format(channel_link))
    return channel_link