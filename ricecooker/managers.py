import uuid
import hashlib
import json
import requests
import tempfile
import shutil
import os
from ricecooker import config
from ricecooker.classes import nodes
from ricecooker.exceptions import InvalidFormatException
from le_utils.constants import file_formats

""" ChannelManager: used to process channel and communicate to content curation server
    @param channel (Channel to process)
    @param verbose (boolean indicating whether to print statements)
"""
class ChannelManager:
    def __init__(self, channel, domain, verbose=False):
        self.channel = channel # Channel to process
        self.verbose = verbose # Determines whether to print process
        self.domain = domain # Domain to upload channel to
        self._file_mapping = {} # Used to keep track of files and their respective metadata


    """ process_tree: sets ids and processes files
        @param node (node to process)
        @param parent (parent of node being processed)
        @return None
    """
    def process_tree(self, node, parent=None):
        if not isinstance(node, nodes.Channel):
            node.set_ids(self.channel._internal_domain, parent.node_id)
            node.files = self.download_files(node.files)

            if isinstance(node, nodes.Exercise):
                mapping, file_list = node.get_all_files()
                self._file_mapping.update(mapping)
                node.files += file_list

        for child_node in node.children:
            self.process_tree(child_node, node)

    """ download_files: downloads files to local storage
        @param files (list of files to download)
        @return list of file hashes and extensions
    """
    def download_files(self,files):
        hashes = [] # list of downloaded files (format:[{hash}.{ext}, {hash}.{ext}...]
        all_file_extensions = [key for key, value in file_formats.choices]
        for f in files:
            file_data = f.split('/')[-1]
            if self.verbose:
                print("\tDownloading {0}...".format(file_data))

            extension = None
            if file_data.split(".")[-1] not in all_file_extensions:
                extension = '.{}'.format(file_formats.PNG)

            filename, original_filename, source_url, file_size = nodes.download_file(f, extension=extension)
            hashes += [filename]
            self._file_mapping.update({filename : {'original_filename': original_filename, 'source_url': source_url, 'size': file_size, 'preset': True}})
        return hashes


    """ get_file_diff: retrieves list of files that do not exist on content curation server
        @return list of files that are not on content curation server
    """
    def get_file_diff(self):
        response = requests.post(config.file_diff_url(self.domain), data=json.dumps([key for key, value in self._file_mapping.items()]))
        response.raise_for_status()
        return json.loads(response._content.decode("utf-8"))


    """ upload_files: uploads files to content curation server
        @param file_list (list of files to upload)
        @return None
    """
    def upload_files(self, file_list):
        for f in file_list:
            with  open(config.get_storage_path(f), 'rb') as file_obj:
                response = requests.post(config.file_upload_url(self.domain), files={'file': file_obj})
                response.raise_for_status()


    """ upload_tree: sends processed channel data to content curation to create tree
        @return link to open newly created channel
    """
    def upload_tree(self):
        payload = {
            "channel_data":self.channel.to_dict(),
            "content_data": [child.to_dict() for child in self.channel.children],
            "file_data": self._file_mapping,
        }
        response = requests.post(config.create_channel_url(self.domain), data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        return config.open_channel_url(new_channel['invite_id'], new_channel['new_channel'], self.domain)