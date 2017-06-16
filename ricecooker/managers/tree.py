import json

from .. import config


class ChannelManager:
    """ Manager for handling channel tree structure and communicating to server

        Attributes:
            channel (Channel): channel that manager is handling
    """
    def __init__(self, channel):
        self.channel = channel  # Channel to process
        self.uploaded_files = []
        self.failed_node_builds = []
        self.failed_uploads = []

    def validate(self):
        """ validate: checks if tree structure is valid
            Args: None
            Returns: boolean indicating if tree is valid
        """
        return self.channel.test_tree()

    def process_tree(self, channel_node):
        """
        Returns a list of all file names associated with a tree. Profiling suggests using a global list with `extend`
        is faster than using a global set or deque.
        :param channel_node: Root node of the channel being processed
        :return: The list of unique file names in `channel_node`.
        """
        file_names = []
        self.process_tree_recur(file_names, channel_node)
        return [x for x in set(file_names) if x]  # Remove any duplicate or null files

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
                title = "{0} {id}".format(f.node.kind.capitalize(), id=f.node.source_id)\
                        if f.node else "{0} {id}".format("Question", id=f.assessment_item.source_id)
                file_identifier = f.__dict__
                if hasattr(f, 'path') and f.path:
                    file_identifier = f.path
                elif hasattr(f, 'youtube_url') and f.youtube_url:
                    file_identifier = f.youtube_url
                config.LOGGER.warning("\t{0}: {id} \n\t   {err}".format(title, id=file_identifier, err=f.error))
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
                        self.failed_uploads.append(f)
        finally:
            config.PROGRESS_MANAGER.set_uploading(self.uploaded_files)

    def reattempt_upload_fails(self):
        """ reattempt_upload_fails: uploads failed files to server
            Args: None
            Returns: None
        """
        if len(self.failed_uploads) > 0:
            config.LOGGER.info("\nReattempting to upload {0} file(s)...".format(len(self.failed_uploads)))
            self.upload_files(self.failed_uploads)

    def upload_channel_structure(self):
        config.LOGGER.info('   Uploading structure of channel {0}'.format(self.channel.title))

        channel_structure = {}
        self.fill_channel_structure(channel_structure, self.channel, 0)
        payload = {
            'channel_id': self.channel.to_dict()['id'],
            'channel_structure': channel_structure,
        }
        response = config.SESSION.post(config.channel_structure_upload_url(), data=json.dumps(payload, sort_keys=False))
        response.raise_for_status()

        new_channel = json.loads(response._content.decode('utf-8'))

        return None, None  # new_channel['channel_id'], new_channel['channel_link']

    def fill_channel_structure(self, cur_dict, cur_node, sort_order):
        children_dict = {}
        child_sort_order = 0
        for child in cur_node.children:
            self.fill_channel_structure(children_dict, child, child_sort_order)
            child_sort_order += 1
        cur_dict[cur_node.hashed_file_name] = (sort_order, children_dict)

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
