
import json
import requests
import os
import sys
from .. import config
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
        self.failed_uploads=[]

    def validate(self):
        """ validate: checks if tree structure is valid
            Args: None
            Returns: boolean indicating if tree is valid
        """
        return self.channel.test_tree()

    def process_tree(self, node, parent=None):
        """ process_tree: processes files
            Args:
                node (Node): node to process
                parent (Node): parent of node being processed
            Returns: None
        """
        from ..classes import nodes

        # If node is not a channel, download files
        if isinstance(node, nodes.Channel):
            if node.thumbnail is not None and node.thumbnail != "":
                file_data = config.DOWNLOADER.download_file(node.thumbnail, "Channel Thumbnail", default_ext=file_formats.PNG)
                node.thumbnail = file_data['filename'] if file_data else ""
        else:
            node.files = config.DOWNLOADER.download_files(node.files, "Node {}".format(node.source_id))

            # Get the thumbnail if provided or needs to be derived
            thumbnail = None
            if node.thumbnail is not None:
                thumbnail = config.DOWNLOADER.download_file(node.thumbnail, "Node {}".format(node.source_id), default_ext=file_formats.PNG, preset=node.thumbnail_preset)
            elif isinstance(node, nodes.Video) and node.derive_thumbnail:
                thumbnail = config.DOWNLOADER.derive_thumbnail(config.get_storage_path(node.files[0]['filename']), "Node {}".format(node.source_id))

            if thumbnail:
                node.files.append(thumbnail)

            # If node is an exercise, process images for exercise
            if isinstance(node, nodes.Exercise):
                node.process_questions()

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

        # If node is a video, compress any high resolution videos
        if isinstance(node, nodes.Video):
            for f in node.files:
                if f['preset'] == format_presets.VIDEO_HIGH_RES:
                    config.LOGGER.info("\tCompressing video: {}\n".format(node.title))
                    compressed = config.DOWNLOADER.compress_file(config.get_storage_path(f['filename']), "Node {}".format(node.source_id))
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
            response = config.SESSION.post(config.file_diff_url(), data=json.dumps(chunk))
            response.raise_for_status()
            file_diff_result += json.loads(response._content.decode("utf-8"))
            file_count += len(chunk)
            config.LOGGER.info("\n\tGot file diff for {0} out of {1} files".format(file_count, total_count))

        return file_diff_result

    def upload_files(self, file_list):
        """ upload_files: uploads files to server
            Args:
                file_list (str): list of files to upload
            Returns: None
        """
        counter = 0
        files_to_upload = list(set(file_list) - set(self.uploaded_files)) # In case restoring from previous session
        config.LOGGER.info("\nUploading {0} new file(s) to Kolibri Studio...".format(len(files_to_upload)))
        try:
            for f in files_to_upload:
                with  open(config.get_storage_path(f), 'rb') as file_obj:
                    response = config.SESSION.post(config.file_upload_url(),  files={'file': file_obj})
                    if response.status_code == 200:
                        response.raise_for_status()
                        self.uploaded_files += [f]
                        counter += 1
                        config.LOGGER.info("\n\tUploaded {0} ({count}/{total}) ".format(f, count=counter, total=len(files_to_upload)))
                    else:
                        self.failed_uploads += [f]
        finally:
            config.PROGRESS_MANAGER.set_uploading(self.uploaded_files)

    def reattempt_upload_fails(self):
        """ reattempt_upload_fails: uploads failed files to server
            Args: None
            Returns: None
        """
        self.upload_files(self.failed_uploads)

    def upload_tree(self):
        """ upload_tree: sends processed channel data to server to create tree
            Args: None
            Returns: link to uploadedchannel
        """
        root, channel_id = self.add_channel()
        self.add_nodes(root, self.channel)
        if self.check_failed(print_warning=False):
            failed = self.failed_node_builds
            self.failed_node_builds = []
            self.reattempt_failed(failed)
            self.check_failed()
        channel_id, channel_link = self.commit_channel(channel_id)
        return channel_id, channel_link

    def reattempt_failed(self, failed):
        for node in failed:
            config.LOGGER.info("\tReattempting {0}".format(str(node[1])))
            for f in node[1].files:
                # Attempt to upload file
                with  open(config.get_storage_path(f['filename']), 'rb') as file_obj:
                    response = config.SESSION.post(config.file_upload_url(),  files={'file': file_obj})
                    response.raise_for_status()
                    self.uploaded_files += [f['filename']]
            # Attempt to create node
            self.add_nodes(node[0], node[1])

    def check_failed(self, print_warning=True):
        if len(self.failed_node_builds) > 0:
            if config.WARNING and print_warning:
                sys.stderr.write("\nWARNING: The following nodes have one or more descendants that could not be created:")
                for node in self.failed_node_builds:
                    sys.stderr.write("\n\t{}".format(str(node[1])))
            else:
                sys.stderr.write("\nFailed to create descendants for {} node(s).".format(len(self.failed_node_builds)))
            return True
        else:
            config.LOGGER.info("   All nodes were created successfully.")
        return False

    def add_channel(self):
        """ add_channel: sends processed channel data to server to create tree
            Args: None
            Returns: link to uploadedchannel
        """
        config.LOGGER.info("   Creating channel {0}".format(self.channel.title))
        payload = {
            "channel_data":self.channel.to_dict(),
        }
        response = config.SESSION.post(config.create_channel_url(), data=json.dumps(payload))
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
        # if the current node has no children, no need to continue
        if not current_node.children:
            return

        config.LOGGER.info("{indent}Processing {title} ({kind})".format(indent="   " * indent, title=current_node.title, kind=current_node.__class__.__name__))
        payload = {
            'root_id': root_id,
            'content_data': [child.to_dict() for child in current_node.children]
        }
        response = config.SESSION.post(config.add_nodes_url(), data=json.dumps(payload))
        if response.status_code != 200:
            self.failed_node_builds += [(root_id, current_node)]
        else:
            response_json = json.loads(response._content.decode("utf-8"))

            for child in current_node.children:
                self.add_nodes(response_json['root_ids'][child.get_node_id().hex], child, indent + 1)

    def commit_channel(self, channel_id):
        """ commit_channel: commits channel to Kolibri Studio
            Args:
                channel_id (str): channel's id on Kolibri Studio
            Returns: channel id and link to uploadedchannel
        """
        payload = {
            "channel_id":channel_id,
        }
        response = config.SESSION.post(config.finish_channel_url(), data=json.dumps(payload))
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
        response = config.SESSION.post(config.publish_channel_url(), data=json.dumps(payload))
        response.raise_for_status()
