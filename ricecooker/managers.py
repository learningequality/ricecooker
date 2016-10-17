import uuid
import hashlib
import json
import requests
from requests_file import FileAdapter
import tempfile
import shutil
import os
from io import BytesIO
from PIL import Image
import validators
import base64
from ricecooker import config
from ricecooker.exceptions import InvalidFormatException
from le_utils.constants import file_formats, exercises, format_presets

WEB_GRAPHIE_URL_REGEX = r'web\+graphie:([^\)]+)'
FILE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'

class DownloadManager:
    all_file_extensions = [key for key, value in file_formats.choices]
    session = requests.Session()

    def __init__(self, verbose=False):
        self.session.mount('file://', FileAdapter())
        self.files = []
        self._file_mapping = {} # Used to keep track of files and their respective metadata
        self.verbose = verbose

    def get_files(self):
        return self.files

    def get_file_mapping(self):
        return self._file_mapping

    def download_graphie(self, path):
        """ download_file: downloads files to local storage
            @param files (list of files to download)
            @return list of file hashes and extensions
        """
        # Initialize paths and hash
        hash = hashlib.md5()
        svg_path = path + ".svg"
        json_path = path + "-data.json"

        # Get svg hash
        rsvg = self.session.get(svg_path, stream=True)
        rsvg.raise_for_status()
        hash = self.get_hash(rsvg, hash)

        # Combine svg hash with json hash
        rjson = self.session.get(json_path, stream=True)
        rjson.raise_for_status()
        hash = self.get_hash(rjson, hash)

        # Download files
        svg_filename = self.download_file(svg_path, hash, '.{}'.format(file_formats.SVG), format_presets.EXERCISE_GRAPHIE, True)
        json_filename = self.download_file(json_path, hash, '-data.{}'.format(file_formats.JSON), format_presets.EXERCISE_GRAPHIE, True)

        return hash.hexdigest(), svg_filename, json_filename

    def get_hash(self, request, hash_to_update):
        for chunk in request:
            hash_to_update.update(chunk)
        return hash_to_update


    def download_image(self, path):
        return self.download_file(path)


    def download_file(self, path, hash=None, default_ext='.{}'.format(file_formats.PNG), preset=None, force_ext=False):
        """ download_file: downloads files to local storage
            @param files (list of files to download)
            @return list of file hashes and extensions
        """
        r = self.session.get(path, stream=True)
        r.raise_for_status()

        # Get extension of file or default if none found
        extension = path.split(".")[-1].lower()
        if force_ext or extension not in self.all_file_extensions:
            extension = default_ext
        else:
            extension = "." + extension

        # Write file to temporary file
        with tempfile.TemporaryFile() as tempf:
            # If a hash was not provided, generate hash during write process
            # Otherwise, just write the file
            if hash is None:
                hash = hashlib.md5()
                for chunk in r:
                    hash.update(chunk)
                    tempf.write(chunk)
            else:
               for chunk in r:
                    tempf.write(chunk)

            # Get file metadata (hashed filename, original filename, size)
            hashstring = hash.hexdigest()
            original_filename = path.split("/")[-1].split(".")[0]
            filename = '{0}{ext}'.format(hashstring, ext=extension)
            file_size = tempf.tell()
            tempf.seek(0)

            # Keep track of downloaded file
            self.files += [filename]
            self._file_mapping.update({filename : {
                'original_filename': original_filename,
                'source_url': path,
                'size': file_size,
                'preset':preset,
            }})

            # Write file to local storage
            with open(config.get_storage_path(filename), 'wb') as destf:
                shutil.copyfileobj(tempf, destf)

            if self.verbose:
                print("\tDownloaded '{0}' to {1}".format(original_filename, filename))

        return filename


    def download_files(self,files):
        """ download_files: downloads files to local storage
            @param files (list of files to download)
            @return list of file hashes and extensions
        """
        file_list = []
        for f in files:
            file_data = f.split('/')[-1]
            file_list += [self.download_file(f)]
        return file_list

    def encode_thumbnail(self, thumbnail):
        """ encode_thumbnail: gets base64 encoding of thumbnail
            Args:
                thumbnail (str): file path or url to channel's thumbnail
            Returns: base64 encoding of thumbnail
        """
        if thumbnail is None:
            return None
        else:
            if validators.url(thumbnail):
                r = self.session.get(thumbnail, stream=True)
                if r.status_code == 200:
                    thumbnail = tempfile.TemporaryFile()
                    for chunk in r:
                        thumbnail.write(chunk)

            img = Image.open(thumbnail)
            width = 200
            height = int((float(img.size[1])*float(width/float(img.size[0]))))
            img.thumbnail((width,height), Image.ANTIALIAS)
            bufferstream = BytesIO()
            img.save(bufferstream, format="PNG")
            return "data:image/png;base64," + base64.b64encode(bufferstream.getvalue()).decode('utf-8')



""" ChannelManager: used to process channel and communicate to content curation server
    @param channel (Channel to process)
    @param verbose (boolean indicating whether to print statements)
"""
class ChannelManager:

    def __init__(self, channel, domain, verbose=False):
        self.channel = channel # Channel to process
        self.verbose = verbose # Determines whether to print process
        self.domain = domain # Domain to upload channel to
        self.downloader = DownloadManager(verbose)

    """ process_tree: sets ids and processes files
        @param node (node to process)
        @param parent (parent of node being processed)
        @return None
    """
    def process_tree(self, node, parent=None):
        from ricecooker.classes import nodes
        if not isinstance(node, nodes.Channel):
            node.set_ids(self.channel._internal_domain, parent.node_id)
            node.files = self.downloader.download_files(node.files)

            if isinstance(node, nodes.Exercise):
                if self.verbose:
                    print("  *** Processing images for exercise: {}".format(node.title))
                node.process_questions(self.downloader)

        for child_node in node.children:
            self.process_tree(child_node, node)


    """ get_file_diff: retrieves list of files that do not exist on content curation server
        @return list of files that are not on content curation server
    """
    def get_file_diff(self):
        response = requests.post(config.file_diff_url(self.domain), data=json.dumps(self.downloader.get_files()))
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
            "file_data": self.downloader._file_mapping,
        }
        response = requests.post(config.create_channel_url(self.domain), data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        return config.open_channel_url(new_channel['invite_id'], new_channel['new_channel'], self.domain)