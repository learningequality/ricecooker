import json
import random
import sys
import webbrowser

import requests
from requests.exceptions import HTTPError

from . import __version__
from . import config
from .classes.nodes import ChannelNode
from .managers.tree import ChannelManager
from .utils.slack import send_slack_notification


def uploadchannel_wrapper(chef, args, options):
    """
    Call the `uploadchannel` function with combined `args` and `options`.
    Args:
        args (dict): chef command line arguments
        options (dict): extra key=value options given on the command line
    """
    args_and_options = args.copy()
    args_and_options.update(options)
    uploadchannel(chef, **args_and_options)


def uploadchannel(  # noqa: C901
    chef,
    command="uploadchannel",
    update=False,
    thumbnails=False,
    download_attempts=3,
    token="#",
    prompt=False,
    publish=False,
    compress=False,
    stage=False,
    **kwargs,
):
    """uploadchannel: Upload channel to Kolibri Studio
    Args:
        chef (SushiChef subclass): class that implements the construct_channel method
        command (str): the action we want to perform in this run
        update (bool): indicates whether to re-download files (optional)
        thumbnails (bool): indicates whether to automatically derive thumbnails from content (optional)
        download_attempts (int): number of times to retry downloading files (optional)
        token (str): content server authorization token
        prompt (bool): indicates whether to prompt user to open channel when done (optional)
        publish (bool): indicates whether to automatically publish channel (optional)
        compress (bool): indicates whether to compress larger files (optional)
        stage (bool): indicates whether to stage rather than deploy channel (optional)
        kwargs (dict): extra keyword args will be passed to construct_channel (optional)
    Returns: (str) link to access newly created channel
    """

    # Set configuration settings
    config.UPDATE = update
    config.COMPRESS = chef.get_setting("compress", False)
    config.VIDEO_HEIGHT = chef.get_setting("video-height", None)
    config.THUMBNAILS = chef.get_setting("thumbnails", False)
    config.STAGE = stage
    config.PUBLISH = publish
    config.FILE_PIPELINE = chef.file_pipeline

    # Set max retries for downloading
    config.DOWNLOAD_SESSION.mount(
        "http://", requests.adapters.HTTPAdapter(max_retries=int(download_attempts))
    )
    config.DOWNLOAD_SESSION.mount(
        "https://", requests.adapters.HTTPAdapter(max_retries=int(download_attempts))
    )

    config.DOWNLOAD_SESSION.auth = chef.auth

    if not command == "dryrun":
        # Authenticate user and check current Ricecooker version
        username, token = authenticate_user(token)
        config.LOGGER.info("Logged in with username {0}".format(username))
        config.DOWNLOAD_SESSION.headers.update(
            {"User-Agent": f"Ricecooker/{__version__} bot ({username})"}
        )
        check_version_number()
    else:
        username = ""
        token = ""

    config.LOGGER.info("\n\n***** Starting channel build process *****\n\n")

    if hasattr(chef, "download_content"):
        chef.download_content()

    # TODO load csv if exists
    metadata_dict = chef.load_channel_metadata_from_csv()

    # Construct channel
    config.LOGGER.info("Calling construct_channel... ")
    channel = chef.construct_channel(**kwargs)
    if "sample" in kwargs and kwargs["sample"]:
        channel = select_sample_nodes(channel, size=kwargs["sample"])

    # Set initial tree
    tree = create_initial_tree(channel)

    # Early permission check: Try creating the channel before downloading/uploading files
    # This will fail fast if the user lacks edit permissions
    # Fixes issues #95 and #434 by avoiding wasted downloads/uploads
    if command != "dryrun":
        config.LOGGER.info("Checking channel permissions...")
        try:
            tree.root_id, tree.channel_id = tree.add_channel()
        except Exception:
            sys.exit(1)

    # Download files
    config.LOGGER.info("")
    config.LOGGER.info("Downloading files...")
    files_to_diff = process_tree_files(tree)

    # Apply any modifications to chef
    chef.apply_modifications(channel, metadata_dict)
    # Save the data about the current run in chefdata/
    chef.save_channel_tree_as_json(channel)

    chef.save_channel_metadata_as_csv(channel)

    if command == "dryrun":
        config.LOGGER.info("Command is dryrun so we are not uploading channel.")
        return

    # Get file diff
    config.LOGGER.info("")
    config.LOGGER.info("Getting file diff...")
    file_diff = get_file_diff(tree, files_to_diff)

    # Upload files
    config.LOGGER.info("")
    config.LOGGER.info("Uploading files...")
    upload_files(tree, file_diff)

    # Create channel on Kolibri Studio
    config.LOGGER.info("")
    config.LOGGER.info("Creating channel...")
    channel_link, channel_id = create_tree(tree)

    # Publish tree if flag is set to True
    if config.PUBLISH:
        config.LOGGER.info("")
        config.LOGGER.info("Publishing channel...")
        publish_tree(tree, channel_id)

    # Open link on web browser (if specified) and return new link
    config.LOGGER.info("\n\nDONE: Channel created at {0}\n".format(channel_link))
    if prompt and prompt_yes_or_no("Would you like to open your channel now?"):
        config.LOGGER.info("Opening channel... ")
        webbrowser.open_new_tab(channel_link)

    if config.SLACK_WEBHOOK_URL:
        send_slack_notification(tree.channel, channel_link)

    return channel_link


def authenticate_user(token):
    """
    This function adds the studio Authorization `token` header to `config.SESSION`
    and checks if the token is valid by performing a test call on the Studio API.
    Args:
        token (str): Studio authorization token
    Returns:
        username, token: Studio username and token if authentication worked
    """
    config.SESSION.headers.update({"Authorization": "Token {0}".format(token)})
    auth_endpoint = config.authentication_url()
    try:
        response = config.SESSION.post(auth_endpoint)
        response.raise_for_status()
        user = json.loads(response._content.decode("utf-8"))
        return user["username"], token
    except HTTPError:
        config.LOGGER.error("Studio token rejected by server " + auth_endpoint)
        sys.exit()


def check_version_number():
    response = config.SESSION.post(
        config.check_version_url(), data=json.dumps({"version": __version__})
    )
    response.raise_for_status()
    result = json.loads(response._content.decode("utf-8"))

    if result["status"] == 0:
        config.LOGGER.info(result["message"])
    elif result["status"] == 1:
        config.LOGGER.warning(result["message"])
    elif result["status"] == 2:
        config.LOGGER.error(result["message"])
        if not prompt_yes_or_no("Continue anyways?"):
            sys.exit()
    else:
        config.LOGGER.error(result["message"])
        sys.exit()


def prompt_yes_or_no(message):
    """prompt_yes_or_no: Prompt user to reply with a y/n response
    Args: None
    Returns: None
    """
    user_input = input("{} [y/n]:".format(message)).lower()
    if user_input.startswith("y"):
        return True
    elif user_input.startswith("n"):
        return False
    else:
        return prompt_yes_or_no(message)


def create_initial_tree(channel):
    """create_initial_tree: Create initial tree structure
    Args:
        channel (Channel): channel to construct
    Returns: tree manager to run rest of steps
    """
    # Create channel manager with channel data
    config.LOGGER.info("   Setting up initial channel structure... ")
    tree = ChannelManager(channel)

    # Make sure channel structure is valid
    config.LOGGER.info("   Validating channel structure...")
    channel.print_tree()
    tree.validate()
    config.LOGGER.info("   Tree is valid")
    return tree


def process_tree_files(tree):
    """process_tree_files: Download files from nodes
    Args:
        tree (ChannelManager): manager to handle communication to Kolibri Studio
    Returns: list of files to check against Kolibri Studio
    """
    # Fill in values necessary for next steps
    config.LOGGER.info("Processing content...")
    files_to_diff = tree.process_tree()
    tree.check_for_files_failed()
    return files_to_diff


def get_file_diff(tree, files_to_diff):
    """get_file_diff: Download files from nodes
    Args:
        tree (ChannelManager): manager to handle communication to Kolibri Studio
    Returns: list of files that are not on Kolibri Studio
    """
    # Determine which files have not yet been uploaded to the CC server
    config.LOGGER.info("  Checking if files exist on Kolibri Studio...")
    file_diff = tree.get_file_diff(files_to_diff)
    return file_diff


def upload_files(tree, file_diff):
    """upload_files: Upload files to Kolibri Studio
    Args:
        tree (ChannelManager): manager to handle communication to Kolibri Studio
        file_diff ([str]): list of files to upload
    Returns: None
    """
    # Upload new files to CC
    config.LOGGER.info(
        "  Uploading {0} new file(s) to Kolibri Studio...".format(len(file_diff))
    )
    tree.upload_files(file_diff)
    tree.reattempt_upload_fails()
    return file_diff


def create_tree(tree):
    """create_tree: Upload tree to Kolibri Studio
    Args:
        tree (ChannelManager): manager to handle communication to Kolibri Studio
    Returns: channel id of created channel and link to channel
    """
    # Create tree
    config.LOGGER.info("Creating tree on Kolibri Studio...")
    channel_id, channel_link = tree.upload_tree()
    return channel_link, channel_id


def publish_tree(tree, channel_id):
    """publish_tree: Publish tree to Kolibri
    Args:
        tree (ChannelManager): manager to handle communication to Kolibri Studio
        channel_id (str): id of channel to publish
    Returns: None
    """
    config.LOGGER.info("Publishing tree to Kolibri... ")
    tree.publish(channel_id)


def select_sample_nodes(channel, size=10, seed=42):  # noqa: C901
    """
    Build a sample tree of `size` leaf nodes from the channel `channel` to use
    for debugging chef functionality without uploading the whole tree.
    """
    config.LOGGER.info("Selecting a sample of size " + str(size))

    # Step 1. channel to paths
    node_paths = []  # list of tuples of the form (topic1, topic2, leafnode)

    def walk_tree(parents_path, subtree):
        for child in subtree.children:
            child_path = parents_path + (child,)
            if child.children:
                # recurse
                walk_tree(child_path, child)
            else:
                # emit leaf node
                node_paths.append(child_path)

    walk_tree((), channel)

    # Step 2. sample paths
    random.seed(seed)
    sample_paths = random.sample(node_paths, size)
    for node_path in sample_paths:
        for node in node_path:
            if node.children:
                node.children = []  # empty children to clear old tree structure

    # Step 3. paths to channel_sample
    channel_sample = ChannelNode(
        source_domain=channel.source_domain,
        source_id=channel.source_id + "-sample",
        title="Sample from " + channel.title,
        thumbnail=channel.thumbnail,
        language=channel.language,
        description="Sample from " + channel.description,
    )

    def attach(parent, node_path):
        if len(node_path) == 1:
            # leaf node
            try:
                parent.add_child(node_path[0])
            except TypeError:
                raise NotImplementedError(
                    "--sample mode is not supported for channels with curriculum structure nodes"
                )
        else:
            child = node_path[0]
            if not any(c.source_id == child.source_id for c in parent.children):
                try:
                    parent.add_child(child)
                except TypeError:
                    raise NotImplementedError(
                        "--sample mode is not supported for channels with curriculum structure nodes"
                    )
            attach(child, node_path[1:])

    for node_path in sample_paths:
        attach(channel_sample, node_path)

    return channel_sample
