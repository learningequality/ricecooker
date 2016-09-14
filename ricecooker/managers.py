import uuid
import hashlib
import json
import requests
import tempfile
import shutil
import os
from fle_utils import constants
from ricecooker import classes
from ricecooker.exceptions import InvalidFormatException

class ChannelManager:
    def __init__(self, channel, root):
        self.channel = channel
        self.root = root
        self.channel._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.channel.domain)
        self.channel._internal_channel_id = uuid.uuid5(self.channel._internal_domain, self.channel.id.hex)
        self.root.set_ids(self.channel._internal_domain, self.channel.id)

    def guess_content_kind(self, data):
        if 'file' in data and len(data['file']) > 0:
            data['file'] = [data['file']] if isinstance(data['file'], str) else data['file']
            for f in data['file']:
                ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
                if ext in constants.CK_MAPPING:
                    return constants.CK_MAPPING[ext]
            raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in constants.CK_MAPPING.items()]))
        else:
            return constants.CK_TOPIC

    def build_tree(self, content_metadata):
        print("Building tree...")
        self._build_tree(content_metadata, self.root)
        return self.channel

    def _build_tree(self, node_data, parent):
        for node in node_data:
            new_node = self._generate_node(node)
            new_node.set_ids(self.channel._internal_domain, parent.node_id)
            if 'children' in node:
                self._build_tree(node['children'], new_node)
            if 'file' in node:
                files = [node['file']] if isinstance(node['file'], str) else node['file']
                new_node.files = self.download_files(files)
            parent.children += [new_node]

    def _generate_node(self, node):
        kind = self.guess_content_kind(node)
        description = node['description'] if 'description' in node else None
        author = node['author'] if 'author' in node else None
        license = node['license'] if 'license' in node else None
        if kind == constants.CK_TOPIC:
            return classes.Topic(
                id=node['id'],
                title=node['title'],
                description=description,
                author=author,
            )
        elif kind == constants.CK_VIDEO:
            return classes.Video(
                id=node['id'],
                title=node['title'],
                description=description,
                author=author,
                license=license,
            )
        elif kind == constants.CK_AUDIO:
            return classes.Audio(
                id=node['id'],
                title=node['title'],
                description=description,
                author=author,
                license=license,
            )
        elif kind == constants.CK_DOCUMENT:
            return classes.Document(
                id=node['id'],
                title=node['title'],
                description=description,
                author=author,
                license=license,
            )
        elif kind == constants.CK_EXERCISE:
            return classes.Exercise(
                id=node['id'],
                title=node['title'],
                description=description,
                author=author,
                license=license,
            )

    def download_files(self,files):
        hash = hashlib.md5()
        hashes = []

        for f in files:
            print("\tDownloading {0}...".format(f))
            r = requests.get(f, stream=True)
            r.raise_for_status()
            with tempfile.TemporaryFile() as tempf:
                for chunk in r:
                    hash.update(chunk)
                    tempf.write(chunk)

                hashstring = hash.hexdigest()
                filename = '{0}{ext}'.format(hashstring, ext=os.path.splitext(f)[-1])

                hashes += [filename]

                tempf.seek(0)

                with open(filename, 'wb') as destf:
                    shutil.copyfileobj(tempf, destf)
        return hashes

# catalog_all_leaf_nodes()
# md5_files(tree)
# cc_server_file_diff(tree)
# upload_tree(tree)