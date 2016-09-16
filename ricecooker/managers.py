import uuid
import hashlib
import json
import requests
import tempfile
import shutil
import os
from fle_utils import constants
from ricecooker import classes, config
from ricecooker.exceptions import InvalidFormatException

class ChannelManager:
    def __init__(self, channel, verbose=False):
        self.channel = channel
        self.verbose = verbose
        self._nodes = []
        self._file_mapping = {}

    def process_tree(self, node, parent=None):
        if not isinstance(node, classes.Channel):
            node.set_ids(self.channel._internal_domain, parent.node_id)
            node.files = self.download_files(node.files)
            self._nodes += [node]
        for child_node in node.children:
            self.process_tree(child_node, node)

    def download_files(self,files):
        hash = hashlib.md5()
        hashes = []

        for f in files:
            if self.verbose:
                print("\tDownloading {0}...".format(f.split('/')[-1]))
            r = requests.get(f, stream=True)
            r.raise_for_status()
            with tempfile.TemporaryFile() as tempf:
                for chunk in r:
                    hash.update(chunk)
                    tempf.write(chunk)

                hashstring = hash.hexdigest()
                original_filename = f.split("/")[-1].split(".")[0]
                filename = '{0}{ext}'.format(hashstring, ext=os.path.splitext(f)[-1])
                hashes += [filename]
                file_size = tempf.tell()

                tempf.seek(0)

                with open(filename, 'wb') as destf:
                    self._file_mapping.update({filename : {'original_filename': original_filename, 'source_url': f, 'size': file_size}})
                    shutil.copyfileobj(tempf, destf)
        return hashes

    def get_file_diff(self):
        response = requests.post(config.file_diff_url(), data=json.dumps([key for key, value in self._file_mapping.items()]))
        return json.loads(response._content.decode("utf-8"))

    def upload_files(self, file_list):
        for f in file_list:
            with  open(f, 'rb') as file_obj:
                response = requests.post(config.file_upload_url(), files={'file': file_obj})
                response.raise_for_status()

    def upload_tree(self):
        payload = {
            "channel_data":self.channel.to_dict(),
            "content_data": [child.to_dict() for child in self.channel.children],
            "file_data": self._file_mapping,
        }
        response = requests.post(config.create_channel_url(), data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        return config.open_channel_url(new_channel['invite_id'], new_channel['new_channel'])