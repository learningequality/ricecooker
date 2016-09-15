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
    def __init__(self, channel, root):
        self.channel = channel
        self.root = root
        self.channel._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.channel.domain)
        self.channel._internal_channel_id = uuid.uuid5(self.channel._internal_domain, self.channel.id.hex)
        self.root.set_ids(self.channel._internal_domain, self.channel.id)
        self._nodes = []
        self._files = []
        self._file_mapping = {}

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
            self._nodes += [new_node]
            parent.children += [new_node]

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
        print("Getting file diff...")
        file_diff_url = "http://127.0.0.1:8000/api/internal/file_diff"
        response = requests.post(config.FILE_DIFF_URL, data=json.dumps([key for key, value in self._file_mapping.items()]))
        return json.loads(response._content.decode("utf-8"))

    def upload_files(self, file_list):
        print("Uploading {0} file(s) to the content curation server...".format(len(file_list)))
        for f in file_list:
            with  open(f, 'rb') as file_obj:
                response = requests.post(config.FILE_UPLOAD_URL, files={'file': file_obj})
                response.raise_for_status()

    def upload_tree(self):
        print("Creating tree on the content curation server...")
        payload = {
            "channel_data":self.channel.to_dict(),
            "content_data": [child.to_dict() for child in self.root.children],
            "file_data": self._file_mapping,
        }
        response = requests.post(config.CREATE_CHANNEL_URL, data=json.dumps(payload))
        response.raise_for_status()
        return json.loads(response._content.decode("utf-8"))