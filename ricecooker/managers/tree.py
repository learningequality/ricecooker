
import json
import requests
import os
import sys
from ricecooker import config
from le_utils.constants import file_formats, format_presets


class ChannelManager:
    """ Manager for handling channel tree structure and communicating to server

        Attributes:
            channel (Channel): channel that manager is handling
    """
    def __init__(self, channel):
        self.channel = channel # Channel to process
        self.uploaded_files=[]
        self.failed_node_builds=[]

    def validate(self):
        """ validate: checks if tree structure is valid
            Args: None
            Returns: boolean indicating if tree is valid
        """
        return self.channel.test_tree()

    def set_relationship(self, node, parent=None):
        """ set_relationship: sets ids
            Args:
                node (Node): node to process
                parent (Node): parent of node being processed
            Returns: None
        """
        from ricecooker.classes import nodes

        # If node is not a channel, set ids and download files
        if not isinstance(node, nodes.Channel):
            node.set_ids(self.channel._internal_domain, parent.node_id)

        # Process node's children
        for child_node in node.children:
            self.set_relationship(child_node, node)

    def process_tree(self, node, parent=None):
        """ process_tree: processes files
            Args:
                node (Node): node to process
                parent (Node): parent of node being processed
            Returns: None
        """
        from ricecooker.classes import nodes

        # If node is not a channel, download files
        if isinstance(node, nodes.Channel):
            if node.thumbnail is not None and node.thumbnail != "":
                file_data = config.DOWNLOADER.download_file(node.thumbnail, "Channel Thumbnail", default_ext=file_formats.PNG)
                node.thumbnail = file_data['filename'] if file_data else ""
        else:
            node.files = config.DOWNLOADER.download_files(node.files, "Node {}".format(node.original_id))

            # Get the thumbnail if provided or needs to be derived
            thumbnail = None
            if node.thumbnail is not None:
                thumbnail = config.DOWNLOADER.download_file(node.thumbnail, "Node {}".format(node.original_id), default_ext=file_formats.PNG)
            elif isinstance(node, nodes.Video) and node.derive_thumbnail:
                thumbnail = config.DOWNLOADER.derive_thumbnail(config.get_storage_path(node.files[0]['filename']), "Node {}".format(node.original_id))
            if thumbnail:
                node.files.append(thumbnail)

            # If node is an exercise, process images for exercise
            if isinstance(node, nodes.Exercise):
                if config.VERBOSE:
                    sys.stderr.write("\n\t*** Processing images for exercise: {}".format(node.title))
                node.process_questions()
                if config.VERBOSE:
                    sys.stderr.write("\n\t*** Images for {} have been processed".format(node.title))

        # Process node's children
        for child_node in node.children:
            self.process_tree(child_node, node)

    def check_for_files_failed(self):
        """ check_for_files_failed: print any files that failed during download process
            Args: None
            Returns: None
        """
        if config.DOWNLOADER.has_failed_files():
            if config.WARNING:
                config.DOWNLOADER.print_failed()
            else:
                sys.stderr.write("\n   {} file(s) have failed to download".format(len(config.DOWNLOADER.failed_files)))
        else:
            sys.stderr.write("\n   All files were successfully downloaded")

    def compress_tree(self, node):
        """ compress_tree: compress high resolution files
            Args: None
            Returns: None
        """
        from ricecooker.classes import nodes

        # If node is not a channel, download files
        if isinstance(node, nodes.Video):
            for f in node.files:
                if f['preset'] == format_presets.VIDEO_HIGH_RES:
                    if config.VERBOSE:
                        sys.stderr.write("\n\tCompressing video: {}".format(node.title))
                    compressed = config.DOWNLOADER.compress_file(config.get_storage_path(f['filename']), "Node {}".format(node.original_id))
                    if compressed:
                        f.update(compressed)

        # Process node's children
        for child_node in node.children:
            self.compress_tree(child_node)

    def get_file_diff(self):
        """ get_file_diff: retrieves list of files that do not exist on content curation server
            Args: None
            Returns: list of files that are not on server
        """
        files_to_diff = config.DOWNLOADER.get_files()
        file_diff_result = []
        chunks = [files_to_diff[x:x+1000] for x in range(0, len(files_to_diff), 1000)]
        file_count = 0
        total_count = len(files_to_diff)
        for chunk in chunks:
            response = requests.post(config.file_diff_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)}, data=json.dumps(chunk))
            response.raise_for_status()
            file_diff_result += json.loads(response._content.decode("utf-8"))
            file_count += len(chunk)
            if config.VERBOSE:
                sys.stderr.write("\n\tGot file diff for {0} out of {1} files".format(file_count, total_count))

        return file_diff_result

    def upload_files(self, file_list):
        """ upload_files: uploads files to server
            Args:
                file_list (str): list of files to upload
            Returns: None
        """
        counter = 0
        files_to_upload = list(set(file_list) - set(self.uploaded_files)) # In case restoring from previous session
        if config.VERBOSE:
            sys.stderr.write("\nUploading {0} new file(s) to Kolibri Studio...".format(len(files_to_upload)))
        try:
            for f in files_to_upload:
                with  open(config.get_storage_path(f), 'rb') as file_obj:
                    response = requests.post(config.file_upload_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)},  files={'file': file_obj})
                    response.raise_for_status()
                    self.uploaded_files += [f]
                    counter += 1
                    if config.VERBOSE:
                        sys.stderr.write("\n\tUploaded {0} ({count}/{total}) ".format(f, count=counter, total=len(files_to_upload)))
        finally:
            config.PROGRESS_MANAGER.set_uploading(self.uploaded_files)

    def upload_tree(self):
        """ upload_files: sends processed channel data to server to create tree
            Args: None
            Returns: link to uploadedchannel
        """
        root, channel_id = self.add_channel()
        self.add_nodes(root, self.channel)
        if self.check_failed():
            self.failed_node_builds = []
            self.reattempt_failed()
            self.check_failed()
        channel_id, channel_link = self.commit_channel(channel_id)
        return channel_id, channel_link

    def reattempt_failed(self):
        for node in self.failed_node_builds:
            if config.VERBOSE:
                sys.stderr.write("\n\tReattempting {0}".format(str(node[1])))
            for f in node[1].files:
                # Attempt to upload file
                with  open(config.get_storage_path(f['filename']), 'rb') as file_obj:
                    response = requests.post(config.file_upload_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)},  files={'file': file_obj})
                    response.raise_for_status()
                    self.uploaded_files += [f['filename']]
            # Attempt to create node
            self.add_nodes(node[0], node[1])

    def check_failed(self):
        if len(self.failed_node_builds) > 0:
            if config.WARNING:
                sys.stderr.write("\nWARNING: The following nodes have one or more descendants that could not be created:")
                for node in self.failed_node_builds:
                    sys.stderr.write("\n\t{}".format(str(node[1])))
            else:
                sys.stderr.write("\nFailed to create descendants for {} node(s).".format(len(self.failed_node_builds)))
            return True
        elif config.VERBOSE:
            sys.stderr.write("\n   All nodes were created successfully.")
        return False

    def add_channel(self):
        """ add_channel: sends processed channel data to server to create tree
            Args: None
            Returns: link to uploadedchannel
        """
        if config.VERBOSE:
            sys.stderr.write("\n   Creating channel {0}".format(self.channel.title))
        payload = {
            "channel_data":self.channel.to_dict(),
        }
        response = requests.post(config.create_channel_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)}, data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))

        return new_channel['root'], new_channel['channel_id']

    def add_nodes(self, root_id, current_node, indent=1):
        """ add_nodes: adds processed nodes to tree
            Args:
                root_id (str): id of parent node on Kolibri Studio
                current_node (Node): node to publish children
                indent (int): level of indentation for printing
            Returns: link to uploadedchannel
        """
        if config.VERBOSE:
            sys.stderr.write("\n{indent}Processing {title} ({kind})".format(indent="   " * indent, title=current_node.title, kind=current_node.__class__.__name__))
        payload = {
            'root_id': root_id,
            'content_data': [child.to_dict() for child in current_node.children]
        }
        response = requests.post(config.add_nodes_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)}, data=json.dumps(payload))
        if response.status_code != 200:
            self.failed_node_builds += [(root_id, current_node)]
        else:
            response_json = json.loads(response._content.decode("utf-8"))

            for child in current_node.children:
                self.add_nodes(response_json['root_ids'][child.node_id.hex], child, indent + 1)

    def commit_channel(self, channel_id):
        """ commit_channel: commits channel to Kolibri Studio
            Args:
                channel_id (str): channel's id on Kolibri Studio
            Returns: channel id and link to uploadedchannel
        """
        payload = {
            "channel_id":channel_id,
        }
        response = requests.post(config.finish_channel_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)}, data=json.dumps(payload))
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        channel_link = config.open_channel_url(new_channel['new_channel'])
        return channel_id, channel_link

    def publish(self, channel_id):
        """ publish: publishes tree to Kolibri
            Args:
                channel_id (str): channel's id on Kolibri Studio
            Returns: None
        """
        payload = {
            "channel_id":channel_id,
        }
        response = requests.post(config.publish_channel_url(), headers={"Authorization": "Token {0}".format(config.TOKEN)}, data=json.dumps(payload))
        response.raise_for_status()
