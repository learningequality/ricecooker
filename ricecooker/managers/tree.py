import json
import sys

from .. import config


class ChannelManager:
    """ Manager for handling channel tree structure and communicating to server

        Attributes:
            channel (Channel): channel that manager is handling
    """
    def __init__(self, channel):
        self.channel = channel  # Channel to process
        self.uploaded_files = []
        self.failed_node_builds = {}
        self.failed_uploads = {}

    def validate(self):
        """ validate: checks if tree structure is valid
            Args: None
            Returns: boolean indicating if tree is valid
        """
        return self.channel.validate_tree()

    def process_tree(self, channel_node):
        """
        Returns a list of all file names associated with a tree. Profiling suggests using a global list with `extend`
        is faster than using a global set or deque.
        :param channel_node: Root node of the channel being processed
        :return: The list of unique file names in `channel_node`.
        """
        file_names = []
        self.process_tree_recur(file_names, channel_node)
        return [x for x in set(file_names) if x]  # Remove any duplicate or None filenames

    def process_tree_recur(self, file_names, node):
        """
        Adds the names of all the files associated with the sub-tree rooted by `node` to `file_names` in post-order.
        :param file_names: A global list containing all file names associated with a tree
        :param node: The root of the current sub-tree being processed
        :return: None.
        """
        # Process node's children
        for child_node in node.children:
            self.process_tree_recur(file_names, child_node)  # Call children first in case a tiled thumbnail is needed

        file_names.extend(node.process_files())


    def check_for_files_failed(self):
        """ check_for_files_failed: print any files that failed during download process
            Args: None
            Returns: None
        """
        if len(config.FAILED_FILES) > 0:
            config.LOGGER.error("   {} file(s) have failed to download".format(len(config.FAILED_FILES)))
            for f in config.FAILED_FILES:
                if f.node:              # files associated with a a content node
                    info = "{0} {id}".format(f.node.kind.capitalize(), id=f.node.source_id)
                elif f.assessment_item:  # files associated with an assessment item
                    info = "{0} {id}".format("Question", id=f.assessment_item.source_id)
                else:   # files not associated with a node or an assessment item
                    info = f.__class__.__name__
                file_identifier = f.__dict__
                if hasattr(f, 'path') and f.path:
                    file_identifier = f.path
                elif hasattr(f, 'youtube_url') and f.youtube_url:
                    file_identifier = f.youtube_url
                config.LOGGER.warning("\t{0}: {id} \n\t   {err}".format(info, id=file_identifier, err=f.error))
        else:
            config.LOGGER.info("   All files were successfully downloaded")

    def get_file_diff(self, files_to_diff):
        """ get_file_diff: retrieves list of files that do not exist on content curation server
            Args: None
            Returns: list of files that are not on server
        """
        file_diff_result = []
        chunks = [files_to_diff[x:x+1000] for x in range(0, len(files_to_diff), 1000)]
        file_count = 0
        total_count = len(files_to_diff)
        for chunk in chunks:
            response = config.SESSION.post(config.file_diff_url(), data=json.dumps(chunk))
            response.raise_for_status()
            file_diff_result += json.loads(response._content.decode("utf-8"))
            file_count += len(chunk)
            config.LOGGER.info("\tGot file diff for {0} out of {1} files".format(file_count, total_count))

        return file_diff_result

    def upload_files(self, file_list):
        """ upload_files: uploads files to server
            Args:
                file_list (str): list of files to upload
            Returns: None
        """
        counter = 0
        files_to_upload = list(set(file_list) - set(self.uploaded_files)) # In case restoring from previous session
        try:
            for f in files_to_upload:
                with open(config.get_storage_path(f), 'rb') as file_obj:
                    response = config.SESSION.post(config.file_upload_url(), files={'file': file_obj})
                    if response.status_code == 200:
                        response.raise_for_status()
                        self.uploaded_files.append(f)
                        counter += 1
                        config.LOGGER.info("\tUploaded {0} ({count}/{total}) ".format(f, count=counter, total=len(files_to_upload)))
                    else:
                        self.failed_uploads[f] = response._content.decode('utf-8')
        finally:
            config.PROGRESS_MANAGER.set_uploading(self.uploaded_files)

    def reattempt_upload_fails(self):
        """ reattempt_upload_fails: uploads failed files to server
            Args: None
            Returns: None
        """
        if len(self.failed_uploads) > 0:
            config.LOGGER.info("Reattempting to upload {0} file(s)...".format(len(self.failed_uploads)))
            current_fails = [k for k in self.failed_uploads]
            self.failed_uploads = {}
            self.upload_files(current_fails)

    def upload_tree(self):
        """ upload_tree: sends processed channel data to server to create tree
            Args: None
            Returns: link to uploadedchannel
        """
        from datetime import datetime
        start_time = datetime.now()
        root, channel_id = self.add_channel()
        self.node_count_dict = {"upload_count": 0, "total_count": self.channel.count()}

        config.LOGGER.info("\tPreparing fields...")
        self.truncate_fields(self.channel)

        self.add_nodes(root, self.channel)
        if self.check_failed(print_warning=False):
            failed = self.failed_node_builds
            self.failed_node_builds = {}
            self.reattempt_failed(failed)
            self.check_failed()
        channel_id, channel_link = self.commit_channel(channel_id)
        end_time = datetime.now()
        config.LOGGER.info("Upload time: {time}s".format(time=(end_time - start_time).total_seconds()))
        return channel_id, channel_link

    def truncate_fields(self, node):
        node.truncate_fields()
        for child in node.children:
            self.truncate_fields(child)

    def reattempt_failed(self, failed):
        for node_id in failed:
            node = failed[node_id]
            config.LOGGER.info("\tReattempting {0}s".format(str(node['node'])))
            for f in node['node'].files:
                # Attempt to upload file
                try:
                    assert f.filename, "File failed to download (cannot be uploaded)"
                    with open(config.get_storage_path(f.filename), 'rb') as file_obj:
                        response = config.SESSION.post(config.file_upload_url(), files={'file': file_obj})
                        response.raise_for_status()
                        self.uploaded_files.append(f.filename)
                except AssertionError as ae:
                    config.LOGGER.warning(ae)
            # Attempt to create node
            self.add_nodes(node_id, node['node'])

    def check_failed(self, print_warning=True):
        if len(self.failed_node_builds) > 0:
            if print_warning:
                config.LOGGER.warning("WARNING: The following nodes have one or more descendants that could not be created:")
                for node_id in self.failed_node_builds:
                    node = self.failed_node_builds[node_id]
                    config.LOGGER.warning("\t{} ({})".format(str(node['node']), node['error']))
            else:
                config.LOGGER.error("Failed to create descendants for {} node(s).".format(len(self.failed_node_builds)))
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
        self.channel.truncate_fields()
        payload = {
            "channel_data":self.channel.to_dict(),
        }
        response = config.SESSION.post(config.create_channel_url(), data=json.dumps(payload))
        try:
            response.raise_for_status()
        except Exception:
            config.LOGGER.error("Error connecting to API: {}".format(response.text))
            raise
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

        config.LOGGER.info("({count} of {total} uploaded) {indent}Processing {title} ({kind})".format(
            count=self.node_count_dict['upload_count'],
            total=self.node_count_dict['total_count'],
            indent="   " * indent,
            title=current_node.title,
            kind=current_node.__class__.__name__)
        )

        # Send children in chunks to avoid gateway errors
        try:
            chunks = [current_node.children[x:x+10] for x in range(0, len(current_node.children), 10)]
            for chunk in chunks:
                payload_children = []

                for child in chunk:
                    failed = [f for f in child.files if f.is_primary and (not f.filename or self.failed_uploads.get(f.filename))]
                    if any(failed):
                        if not self.failed_node_builds.get(root_id):
                            error_message = ""
                            for fail in failed:
                                reason = fail.filename + ": " + self.failed_uploads.get(fail.filename) if fail.filename else "File failed to download"
                                error_message = error_message + reason + ", "
                            self.failed_node_builds[root_id] = {'node': current_node, 'error': error_message[:-2]}
                    else:
                        payload_children.append(child.to_dict())
                payload = {
                    'root_id': root_id,
                    'content_data': payload_children
                }

                # When iceqube is integrated, use this method to utilize upload file optimizations
                # response = config.SESSION.post(config.add_nodes_from_file_url(), files={'file': json.dumps(payload)})

                response = config.SESSION.post(config.add_nodes_url(), data=json.dumps(payload))
                if response.status_code != 200:
                    self.failed_node_builds[root_id] = {'node': current_node, 'error': response.reason}
                else:
                    response_json = json.loads(response._content.decode("utf-8"))
                    self.node_count_dict['upload_count'] += len(chunk)

                    if response_json['root_ids'].get(child.get_node_id().hex):
                        for child in chunk:
                            self.add_nodes(response_json['root_ids'].get(child.get_node_id().hex), child, indent + 1)
        except ConnectionError as ce:
            self.failed_node_builds[root_id] = {'node': current_node, 'error': ce}

    def commit_channel(self, channel_id):
        """ commit_channel: commits channel to Kolibri Studio
            Args:
                channel_id (str): channel's id on Kolibri Studio
            Returns: channel id and link to uploadedchannel
        """
        payload = {
            "channel_id":channel_id,
            "stage": config.STAGE,
        }
        response = config.SESSION.post(config.finish_channel_url(), data=json.dumps(payload))
        if response.status_code != 200:
            config.LOGGER.error("")
            config.LOGGER.error("Could not activate channel: {}\n".format(response._content.decode('utf-8')))
            if response.status_code == 403:
                config.LOGGER.error("Channel can be viewed at {}\n\n".format(config.open_channel_url(channel_id, staging=True)))
                sys.exit()
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
