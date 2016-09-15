from fle_utils import constants
from ricecooker.classes import *
from ricecooker.managers import ChannelManager

def createchannel(channel_metadata, content_metadata):
    channel = Channel(
        domain=channel_metadata['domain'],
        channel_id=channel_metadata['channel_id'],
        title=channel_metadata['title'],
        description=channel_metadata['description'],
        thumbnail= channel_metadata['thumbnail'],
    )
    root = Topic(
        id=channel.id.hex,
        title=channel_metadata['title']
    )

    tree = ChannelManager(channel, root)
    tree.build_tree(content_metadata)
    file_diff = tree.get_file_diff()
    tree.upload_files(file_diff)
    channel_id = tree.upload_tree()
    print("Channel created with id: {0}".format(channel_id['new_channel']))
    return channel