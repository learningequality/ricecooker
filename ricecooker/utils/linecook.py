import argparse
import os

from ricecooker.config import LOGGER
from le_utils.constants import content_kinds
from .metadata_provider import path_to_tuple
from .jsontrees import (TOPIC_NODE, VIDEO_NODE, AUDIO_NODE, EXERCISE_NODE,
                        DOCUMENT_NODE, HTML5_NODE)
from .jsontrees import (VIDEO_FILE, AUDIO_FILE, DOCUMENT_FILE, EPUB_FILE, HTML5_FILE,
                        THUMBNAIL_FILE, SUBTITLES_FILE)
from .jsontrees import write_tree_to_json_tree


# LINECOOK CONFIGS
################################################################################
DIR_EXCLUDE_PATTERNS = []
FILE_EXCLUDE_EXTENTIONS = ['.DS_Store', 'Thumbs.db', 'ehthumbs.db', 'ehthumbs_vista.db', '.gitkeep']
FILE_SKIP_PATTENRS = []
FILE_SKIP_THUMBNAILS = []  # global list of paths that correspond to thumbails for other content nodes



# LINECOOK HELPER FUNCTIONS
################################################################################

def chan_path_from_rel_path(rel_path, channeldir):
    """
    Convert `rel_path` form os.walk tuple format to a tuple of directories and
    subdirectories, starting with the `channeldir` folder, e.g.,::

        >>> chan_path_from_rel_path('content/open_stax_zip/Open Stax/Math/Elementary',
                                'content/open_stax_zip/Open Stax')
        'Open Stax/Math/Elementary'
    """
    rel_path_parts = rel_path.split(os.path.sep)
    dirs_before_channeldir = channeldir.split(os.path.sep)[:-1]
    channel_chan_path = []  # path relative to channel root, inclusive
    for idx, part in enumerate(rel_path_parts):
        if idx < len(dirs_before_channeldir) and dirs_before_channeldir[idx]==part:
            continue
        else:
            channel_chan_path.append(part)
    chan_path = os.path.join(*channel_chan_path)
    return chan_path

def rel_path_from_chan_path(chan_path, channeldir, windows=False):
    """
    Convert `chan_path` as obtained from a metadata provider into a `rel_path`
    suitable for accessing the file from the current working directory, e.g.,
    >>> rel_path_from_chan_path('Open Stax/Math', 'content/open_stax_zip/Open Stax')
    'content/open_stax_zip/Open Stax/Math'
    """
    if windows:
        chan_path_list = chan_path.split('\\')
    else:
        chan_path_list = chan_path.split('/')
    chan_path_list.pop(0)  # remove the channel root dir
    rel_path = os.path.join(channeldir, *chan_path_list)
    return rel_path

def get_topic_for_path(channel, chan_path_tuple):
    """
    Given channel (dict) that contains a hierary of TopicNode dicts, we use the
    walk the path given in `chan_path_tuple` to find the corresponding TopicNode.
    """
    assert chan_path_tuple[0] == channel['dirname'], 'Wrong channeldir'
    chan_path_list = list(chan_path_tuple)
    chan_path_list.pop(0)    # skip the channel name

    if len(chan_path_list) == 0:
        return channel

    current = channel
    for subtopic in chan_path_list:
        current = list(filter(lambda d: 'dirname' in d and d['dirname'] == subtopic, current['children']))[0]
    return current



# LINECOOK BUILD JSON TREE
################################################################################

def filter_filenames(filenames):
    """
    Skip files with extentions in `FILE_EXCLUDE_EXTENTIONS` and filenames that
    contain `FILE_SKIP_PATTENRS`.
    """
    filenames_cleaned = []
    for filename in filenames:
        keep = True
        for pattern in FILE_EXCLUDE_EXTENTIONS:
            if filename.endswith(pattern):
                keep = False
        for pattern in FILE_SKIP_PATTENRS:   # This will reject exercises...
            if pattern in filename:
                keep = False
        if keep:
            filenames_cleaned.append(filename)
    return filenames_cleaned

def filter_thumbnail_files(chan_path, filenames, metadata_provider):
    """
    We don't want to create `ContentNode` from thumbnail files.
    """
    thumbnail_files_to_skip = set(os.path.join(*p) for p in metadata_provider.get_thumbnail_paths())
    return [filename for filename in filenames if os.path.join(chan_path, filename) not in thumbnail_files_to_skip]

def keep_folder(raw_path):
    """
    Keep only folders that don't contain patterns in `DIR_EXCLUDE_PATTERNS`.
    """
    keep = True
    for pattern in DIR_EXCLUDE_PATTERNS:
        if pattern in raw_path:
            LOGGER.debug('rejecting', raw_path)
            keep = False
    return keep

def process_folder(channel, rel_path, filenames, metadata_provider):
    """
    Create `ContentNode`s from each file in this folder and the node to `channel`
    under the path `rel_path`.
    """
    LOGGER.debug('IN process_folder ' + str(rel_path) + '     ' + str(filenames))
    if not keep_folder(rel_path):
        return

    chan_path = chan_path_from_rel_path(rel_path, metadata_provider.channeldir)
    chan_path_tuple = path_to_tuple(chan_path)
    chan_path_list = list(chan_path_tuple)
    LOGGER.debug('chan_path_list=' + str(chan_path_list))

    # FIND THE CONTAINING NODE (channel or topic)
    if len(chan_path_list) == 1:
        # CASE CHANNEL ROOT: `rel_path` points to `channeldir`
        # No need to create a topic node here since channel already exists
        containing_node = channel  # attach content nodes in filenames directly to channel

    else:
        # CASE TOPIC FOLDER: `rel_path` points to a channelroot subfolder (a.k.a TopicNode)
        dirname = chan_path_list.pop()  # name of the folder (used as ID for internal lookup)
        topic_parent_node = get_topic_for_path(channel, chan_path_list)

        # read topic metadata to get title and description for the TopicNode
        topic_metadata = metadata_provider.get(chan_path_tuple)
        thumbnail_chan_path =  topic_metadata.get('thumbnail_chan_path', None)
        if thumbnail_chan_path:
            thumbnail_rel_path = rel_path_from_chan_path(thumbnail_chan_path, metadata_provider.channeldir)
        else:
            thumbnail_rel_path = None
        # create TopicNode for this folder
        topic = dict(
            kind=TOPIC_NODE,
            dirname=dirname,
            source_id='sourceid:' + rel_path,
            title=topic_metadata.get('title', dirname),
            description=topic_metadata.get('description', None),
            author=topic_metadata.get('author', None),
            language=topic_metadata.get('language', None),
            license=topic_metadata.get('license', None),
            thumbnail=thumbnail_rel_path,
            children=[],
        )
        topic_parent_node['children'].append(topic)
        containing_node = topic  # attach content nodes in filenames to the newly created topic

    # filter filenames
    filenames_cleaned = filter_filenames(filenames)
    filenames_cleaned2 = filter_thumbnail_files(chan_path, filenames_cleaned, metadata_provider)

    # PROCESS FILES
    for filename in filenames_cleaned2:
        chan_filepath = os.path.join(chan_path, filename)
        chan_filepath_tuple = path_to_tuple(chan_filepath)
        metadata = metadata_provider.get(chan_filepath_tuple)
        node = make_content_node(metadata_provider.channeldir, rel_path, filename, metadata)
        containing_node['children'].append(node)  # attach content node to containing_node


def build_ricecooker_json_tree(args, options, metadata_provider, json_tree_path):
    """
    Download all categories, subpages, modules, and resources from open.edu.
    """
    LOGGER.info('Starting to build the ricecooker_json_tree')

    channeldir = args['channeldir']
    if channeldir.endswith(os.path.sep):
        channeldir.rstrip(os.path.sep)
    channelparentdir, channeldirname = os.path.split(channeldir)
    channelparentdir, channeldirname = os.path.split(channeldir)

    # Ricecooker tree
    channel_info = metadata_provider.get_channel_info()
    thumbnail_chan_path =  channel_info.get('thumbnail_chan_path', None)
    if thumbnail_chan_path:
        thumbnail_rel_path = rel_path_from_chan_path(thumbnail_chan_path, metadata_provider.channeldir)
    else:
        thumbnail_rel_path = None

    ricecooker_json_tree = dict(
        dirname=channeldirname,
        title=channel_info['title'],
        description=channel_info['description'],
        source_domain=channel_info['source_domain'],
        source_id=channel_info['source_id'],
        language=channel_info['language'],
        thumbnail=thumbnail_rel_path,
        children=[],
    )
    channeldir = args['channeldir']
    content_folders = sorted(os.walk(channeldir))

    # MAIN PROCESSING OF os.walk OUTPUT
    ############################################################################
    # TODO(ivan): figure out all the implications of the
    # _ = content_folders.pop(0)  # Skip over channel folder because handled above
    for rel_path, _subfolders, filenames in content_folders:
        LOGGER.info('processing folder ' + str(rel_path))

        # IMPLEMENTATION DETAIL:
        #   - `filenames` contains real files in the `channeldir` folder
        #   - `exercises_filenames` contains virtual files whose sole purpse is to set the
        #     order of nodes within a given topic. Since alphabetical order is used to
        #     walk the files in the `channeldir`, we must "splice in" the exercises here
        if metadata_provider.has_exercises():
            dir_chan_path = chan_path_from_rel_path(rel_path, metadata_provider.channeldir)
            dir_path_tuple = path_to_tuple(dir_chan_path)
            exercises_filenames = metadata_provider.get_exercises_for_dir(dir_path_tuple)
            filenames.extend(exercises_filenames)

        sorted_filenames = sorted(filenames)
        process_folder(ricecooker_json_tree, rel_path, sorted_filenames, metadata_provider)

    # Write out ricecooker_json_tree.json
    write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)
    LOGGER.info('Folder hierarchy walk result stored in ' + json_tree_path)


def make_content_node(channeldir, rel_path, filename, metadata):
    """
    Create ContentNode based on the file extention and metadata provided.
    """
    file_key, file_ext = os.path.splitext(filename)
    ext = file_ext[1:]
    kind = None
    if ext in content_kinds.MAPPING:
        kind = content_kinds.MAPPING[ext]   # guess what kind based on file extension
    elif 'questions' in metadata:
        kind = content_kinds.EXERCISE
    else:
        raise ValueError('Could not find kind for extension ' + str(ext) + ' in content_kinds.MAPPING')

    # Extract metadata fields
    source_id = metadata.get('source_id', None)
    if source_id is None:
        source_id = metadata['chan_path']

    filepath = os.path.join(rel_path, filename)
    title = metadata['title']
    description = metadata.get('description', None)
    author = metadata.get('author', None)
    lang =  metadata.get('language', None)
    license_dict = metadata.get('license', None)
    thumbnail_chan_path =  metadata.get('thumbnail_chan_path', None)
    if thumbnail_chan_path:
        thumbnail_rel_path = rel_path_from_chan_path(thumbnail_chan_path, channeldir)
    else:
        thumbnail_rel_path = None

    if kind == VIDEO_NODE:
        content_node = dict(
            kind=VIDEO_NODE,
            source_id=source_id,
            title=title,
            author=author,
            description=description,
            language=lang,
            license=license_dict,
            derive_thumbnail=True,
            thumbnail=thumbnail_rel_path,
            files=[{'file_type':VIDEO_FILE, 'path':filepath, 'language':lang}], # ffmpeg_settings={"crf": 24},
        )

    elif kind == AUDIO_NODE:
        content_node = dict(
            kind=AUDIO_NODE,
            source_id=source_id,
            title=title,
            author=author,
            description=description,
            language=lang,
            license=license_dict,
            thumbnail=thumbnail_rel_path,
            derive_thumbnail=True,
            files=[{'file_type':AUDIO_FILE, 'path':filepath, 'language':lang}],
        )

    elif kind == DOCUMENT_NODE:
        content_node = dict(
            kind=DOCUMENT_NODE,
            source_id=source_id,
            title=title,
            author=author,
            description=description,
            language=lang,
            license=license_dict,
            thumbnail=thumbnail_rel_path,
            derive_thumbnail=True,
            files=[]
        )
        if ext == 'pdf':
            pdf_file = {
                'file_type':DOCUMENT_FILE,
                'path':filepath,
                'language':lang
            }
            content_node['files'].append(pdf_file)
        elif ext == 'epub':
            epub_file = {
                'file_type':EPUB_FILE,
                'path':filepath,
                'language':lang
            }
            content_node['files'].append(epub_file)
        else:
            raise ValueError('Ext {} not supported for kind {}'.format(ext, kind))

    elif kind == HTML5_NODE:
        content_node = dict(
            kind=HTML5_NODE,
            source_id=source_id,
            title=title,
            author=author,
            description=description,
            language=lang,
            license=license_dict,
            thumbnail=thumbnail_rel_path,
            derive_thumbnail=True,
            files=[{'file_type':HTML5_FILE, 'path':filepath, 'language':lang}],
        )

    elif kind == EXERCISE_NODE:
        content_node = dict(
            kind=EXERCISE_NODE,
            source_id=source_id,
            title=title,
            author=author,
            description=description,
            language=lang,
            license=license_dict,
            exercise_data=metadata['exercise_data'],
            questions=metadata['questions'],
            thumbnail=thumbnail_rel_path,
            derive_thumbnail=False,
            files=[],
        )

    else:
        raise ValueError('Not implemented case for kind ' + str(kind))

    return content_node



# AUTOMATIC REMOVAL OF TRAILING SLASHES FOR chenneldir
################################################################################

class NonFolderError(Exception):
    pass

class FolderExistsAction(argparse.Action):
    """
    Custom argparse action: verify the argument to be a folder (directory).
    The action will strip off trailing slashes from the folder's name.
    """
    def verify_folder_existence(self, folder_name):
        if not os.path.isdir(folder_name):
            message = 'ERROR: {0} is not a folder'.format(folder_name)
            raise NonFolderError(message)
        folder_name = folder_name.rstrip(os.sep)
        return folder_name

    def __call__(self, parser, namespace, values, option_string=None):
        if type(values) == list:
            folders = map(self.verify_folder_existence, values)
        else:
            folders = self.verify_folder_existence(values)
        setattr(namespace, self.dest, folders)
