import codecs
import concurrent.futures
import json
import os
import sys

from requests.exceptions import RequestException

from .. import config


class ChannelManager:
    """Manager for handling channel tree structure and communicating to server

    Attributes:
        channel (Channel): channel that manager is handling
    """

    def __init__(self, channel):
        self.channel = channel  # Channel to process
        self.uploaded_files = []
        self.failed_node_builds = {}
        self.failed_uploads = {}
        self.file_map = {}
        self.all_nodes = []

    def validate(self):
        """validate: checks if tree structure is valid
        Args: None
        Returns: boolean indicating if tree is valid
        """
        if not self.all_nodes:
            self.all_nodes = self.gather_tree_recur([], self.channel)
        valid = True
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.TASK_THREADS
        ) as executor:
            for result in executor.map(self.validate_node, self.all_nodes):
                valid = valid and result
        return valid

    def validate_node(self, node):
        try:
            return node.validate()
        except Exception as e:
            if config.STRICT:
                raise
            else:
                config.LOGGER.warning(str(e))
        return True

    def process_tree(self, channel_node):
        """
        Returns a list of all file names associated with a tree. Profiling suggests using a global list with `extend`
        is faster than using a global set or deque.
        :param channel_node: Root node of the channel being processed
        :return: The list of unique file names in `channel_node`.
        """
        if not self.all_nodes:
            self.all_nodes = self.gather_tree_recur([], self.channel)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.TASK_THREADS
        ) as executor:
            for data in executor.map(self.process_node, self.all_nodes):
                self.file_map.update(data)
        return list(self.file_map.keys())

    def gather_tree_recur(self, nodes, node):
        # Process node's children
        for child_node in node.children:
            self.gather_tree_recur(
                nodes, child_node
            )  # Defer insert until after all descendants in case a tiled thumbnail is needed
        nodes.append(node)
        return nodes

    def process_node(self, node):
        """
        :param node: The root of the current sub-tree being processed
        :return: None.
        """
        node.process_files()

        output = {}

        for node_file in node.files:
            if node_file.get_filename():
                output[node_file.get_filename()] = node_file
        if hasattr(node, "questions"):
            for question in node.questions:
                for question_file in question.files:
                    if question_file.get_filename():
                        output[question_file.get_filename()] = question_file
        return output

    def check_for_files_failed(self):
        """check_for_files_failed: print any files that failed during download process
        Args: None
        Returns: None
        """
        if len(config.FAILED_FILES) > 0:
            config.LOGGER.error(
                "   {} file(s) have failed to download".format(len(config.FAILED_FILES))
            )
            for f in config.FAILED_FILES:
                if f.node:  # files associated with a a content node
                    info = "{0} {id}".format(
                        f.node.kind.capitalize(), id=f.node.source_id
                    )
                elif f.assessment_item:  # files associated with an assessment item
                    info = "{0} {id}".format("Question", id=f.assessment_item.source_id)
                else:  # files not associated with a node or an assessment item
                    info = f.__class__.__name__
                file_identifier = f.__dict__
                if hasattr(f, "path") and f.path:
                    file_identifier = f.path
                elif hasattr(f, "youtube_url") and f.youtube_url:
                    file_identifier = f.youtube_url
                config.LOGGER.warning(
                    "\t{0}: {id} \n\t   {err}".format(
                        info, id=file_identifier, err=f.error
                    )
                )
        else:
            config.LOGGER.info("   All files were successfully downloaded")

    def check_file_exists(self, filename):
        head_response = config.DOWNLOAD_SESSION.head(config.get_storage_url(filename))
        return head_response.status_code == 200

    def get_file_diff(self, files_to_diff):
        """get_file_diff: retrieves list of files that do not exist on content curation server
        Args: None
        Returns: list of files that are not on server
        """
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.TASK_THREADS
        ) as executor:
            return [
                filename
                for filename, exists in zip(
                    files_to_diff, executor.map(self.check_file_exists, files_to_diff)
                )
                if not exists
            ]

    def do_file_upload(self, filename):
        file_data = self.file_map[filename]
        if file_data.skip_upload:
            return
        with open(config.get_storage_path(filename), "rb") as file_obj:
            data = {
                "size": file_data.size,
                "checksum": file_data.checksum,
                "name": file_data.original_filename or file_data.get_filename(),
                "file_format": file_data.extension,
                "preset": file_data.get_preset(),
                "duration": file_data.duration,
            }
            # Workaround for a bug in the Studio upload URL endpoint, whereby
            # it does not currently use the passed in file_format as the default
            # extension.
            name, ext = os.path.splitext(data["name"])
            if not ext:
                data["name"] = "{}.{}".format(name, data["file_format"])
            url_response = config.SESSION.post(config.get_upload_url(), json=data)
            if url_response.status_code == 200:
                response_data = url_response.json()
                upload_url = response_data["uploadURL"]
                content_type = response_data["mimetype"]
                might_skip = response_data["might_skip"]
                if might_skip and self.check_file_exists(filename):
                    return
                b64checksum = (
                    codecs.encode(codecs.decode(file_data.checksum, "hex"), "base64")
                    .decode()
                    .strip()
                )
                headers = {"Content-Type": content_type, "Content-MD5": b64checksum}
                response = config.SESSION.put(
                    upload_url, headers=headers, data=file_obj
                )
                if response.status_code == 200:
                    return
                raise RequestException(
                    "Error uploading file {}, response code: {} - {}".format(
                        filename, response.status_code, response.text
                    )
                )
            else:
                raise RequestException(
                    "Error retrieving upload URL for file {}, response code: {} - {}".format(
                        filename, url_response.status_code, response.text
                    )
                )

    def _handle_upload(self, f):
        try:
            self.do_file_upload(f)
            self.uploaded_files.append(f)
        except Exception as e:
            config.LOGGER.error(e)
            self.failed_uploads[f] = str(e)
            return
        return str(f)

    def upload_files(self, file_list):
        """upload_files: uploads files to server
        Args:
            file_list (str): list of files to upload
        Returns: None
        """
        counter = 0
        files_to_upload = list(
            set(file_list) - set(self.uploaded_files)
        )  # In case restoring from previous session
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=config.TASK_THREADS
            ) as executor:
                # Start the upload operations
                for filename in executor.map(self._handle_upload, files_to_upload):
                    if filename is not None:
                        counter += 1
                        config.LOGGER.info(
                            "\tUploaded {0} ({count}/{total}) ".format(
                                filename, count=counter, total=len(files_to_upload)
                            )
                        )
        finally:
            config.PROGRESS_MANAGER.set_uploading(self.uploaded_files)

    def reattempt_upload_fails(self):
        """reattempt_upload_fails: uploads failed files to server
        Args: None
        Returns: None
        """
        if len(self.failed_uploads) > 0:
            config.LOGGER.info(
                "Reattempting to upload {0} file(s)...".format(len(self.failed_uploads))
            )
            current_fails = [k for k in self.failed_uploads]
            self.failed_uploads = {}
            self.upload_files(current_fails)

    def upload_tree(self):
        """upload_tree: sends processed channel data to server to create tree
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
        config.LOGGER.info(
            "Upload time: {time}s".format(time=(end_time - start_time).total_seconds())
        )
        return channel_id, channel_link

    def truncate_fields(self, node):
        node.truncate_fields()
        for child in node.children:
            self.truncate_fields(child)

    def reattempt_failed(self, failed):
        for node_id in failed:
            node = failed[node_id]
            config.LOGGER.info("\tReattempting {0}s".format(str(node["node"])))
            for f in node["node"].files:
                # Attempt to upload file
                try:
                    assert f.filename, "File failed to download (cannot be uploaded)"
                    self.do_file_upload(f.filename)
                except AssertionError as ae:
                    config.LOGGER.warning(ae)
            # Attempt to create node
            self.add_nodes(node_id, node["node"])

    def check_failed(self, print_warning=True):
        if len(self.failed_node_builds) > 0:
            if print_warning:
                config.LOGGER.warning(
                    "WARNING: The following nodes have one or more descendants that could not be created:"
                )
                for node_id in self.failed_node_builds:
                    node = self.failed_node_builds[node_id]
                    config.LOGGER.warning(
                        "\t{} ({})".format(str(node["node"]), node["error"])
                    )
                    if "content" in node:
                        config.LOGGER.warning(node["content"][:80])
            else:
                config.LOGGER.error(
                    "Failed to create descendants for {} node(s).".format(
                        len(self.failed_node_builds)
                    )
                )
            return True
        else:
            config.LOGGER.info("   All nodes were created successfully.")
        return False

    def add_channel(self):
        """add_channel: sends processed channel data to server to create tree
        Args: None
        Returns: link to uploadedchannel
        """
        config.LOGGER.info("   Creating channel {0}".format(self.channel.title))
        self.channel.truncate_fields()
        payload = {"channel_data": self.channel.to_dict()}
        response = config.SESSION.post(
            config.create_channel_url(), data=json.dumps(payload)
        )
        try:
            response.raise_for_status()
        except Exception:
            config.LOGGER.error("Error connecting to API: {}".format(response.text))
            raise
        new_channel = json.loads(response._content.decode("utf-8"))

        return new_channel["root"], new_channel["channel_id"]

    def add_nodes(self, root_id, current_node, indent=1):  # noqa: C901
        """add_nodes: adds processed nodes to tree
        Args:
            root_id (str): id of parent node on Kolibri Studio
            current_node (Node): node to publish children
            indent (int): level of indentation for printing
        Returns: link to uploadedchannel
        """
        # if the current node has no children, no need to continue
        if not current_node.children:
            return

        config.LOGGER.info(
            "({count} of {total} uploaded) {indent}Processing {title} ({kind})".format(
                count=self.node_count_dict["upload_count"],
                total=self.node_count_dict["total_count"],
                indent="   " * indent,
                title=current_node.title,
                kind=current_node.__class__.__name__,
            )
        )

        # Send children in chunks to avoid gateway errors
        try:
            chunks = [
                current_node.children[x : x + 10]
                for x in range(0, len(current_node.children), 10)
            ]
            for chunk in chunks:
                payload_children = []

                for child in chunk:
                    failed = [
                        f
                        for f in child.files
                        if f.is_primary
                        and (not f.filename or self.failed_uploads.get(f.filename))
                    ]
                    if any(failed):
                        if not self.failed_node_builds.get(root_id):
                            error_message = ""
                            for fail in failed:
                                reason = (
                                    fail.filename
                                    + ": "
                                    + self.failed_uploads.get(fail.filename)
                                    if fail.filename
                                    else "File failed to download"
                                )
                                error_message = error_message + reason + ", "
                            self.failed_node_builds[root_id] = {
                                "node": current_node,
                                "error": error_message[:-2],
                            }
                    else:
                        payload_children.append(child.to_dict())
                payload = {"root_id": root_id, "content_data": payload_children}

                response = config.SESSION.post(
                    config.add_nodes_url(), data=json.dumps(payload)
                )
                if response.status_code != 200:
                    self.failed_node_builds[root_id] = {
                        "node": current_node,
                        "error": response.reason,
                        "content": response.content,
                    }
                else:
                    response_json = json.loads(response._content.decode("utf-8"))
                    self.node_count_dict["upload_count"] += len(chunk)

                    if response_json["root_ids"].get(child.get_node_id().hex):
                        for child in chunk:
                            self.add_nodes(
                                response_json["root_ids"].get(child.get_node_id().hex),
                                child,
                                indent + 1,
                            )
        except ConnectionError as ce:
            self.failed_node_builds[root_id] = {"node": current_node, "error": ce}

    def commit_channel(self, channel_id):
        """commit_channel: commits channel to Kolibri Studio
        Args:
            channel_id (str): channel's id on Kolibri Studio
        Returns: channel id and link to uploadedchannel
        """
        payload = {"channel_id": channel_id, "stage": config.STAGE}
        response = config.SESSION.post(
            config.finish_channel_url(), data=json.dumps(payload)
        )
        if response.status_code != 200:
            config.LOGGER.error("")
            config.LOGGER.error(
                "Could not activate channel: {}\n".format(
                    response._content.decode("utf-8")
                )
            )
            if response.status_code == 403:
                config.LOGGER.error(
                    "Channel can be viewed at {}\n\n".format(
                        config.open_channel_url(channel_id, staging=True)
                    )
                )
                sys.exit()
        response.raise_for_status()
        new_channel = json.loads(response._content.decode("utf-8"))
        channel_link = config.open_channel_url(new_channel["new_channel"])
        return channel_id, channel_link

    def publish(self, channel_id):
        """publish: publishes tree to Kolibri
        Args:
            channel_id (str): channel's id on Kolibri Studio
        Returns: None
        """
        payload = {"channel_id": channel_id}
        response = config.SESSION.post(
            config.publish_channel_url(), data=json.dumps(payload)
        )
        response.raise_for_status()
