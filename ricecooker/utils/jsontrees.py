
import json
import os

from ricecooker.classes import files, nodes, questions
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.exceptions import UnknownFileTypeError, UnknownQuestionTypeError
from ricecooker.classes.nodes import ChannelNode



# CONSTANTS USED TO SELECT APPROPRIATE CLASS DURING DESERIALIZATION FROM JSON
################################################################################
from le_utils.constants import roles

from le_utils.constants import content_kinds
TOPIC_NODE = content_kinds.TOPIC
VIDEO_NODE = content_kinds.VIDEO
AUDIO_NODE = content_kinds.AUDIO
EXERCISE_NODE = content_kinds.EXERCISE
DOCUMENT_NODE = content_kinds.DOCUMENT
HTML5_NODE = content_kinds.HTML5
SLIDESHOW_NODE = content_kinds.SLIDESHOW

# TODO(Ivan): add constants.file_types to le_utils and discuss with Jordan
from le_utils.constants import file_types
VIDEO_FILE = file_types.VIDEO
AUDIO_FILE = file_types.AUDIO
DOCUMENT_FILE = file_types.DOCUMENT
EPUB_FILE = file_types.EPUB
HTML5_FILE = file_types.HTML5
THUMBNAIL_FILE = file_types.THUMBNAIL
SUBTITLES_FILE = file_types.SUBTITLES
SLIDESHOW_IMAGE_FILE = file_types.SLIDESHOW_IMAGE

from le_utils.constants import exercises
INPUT_QUESTION = exercises.INPUT_QUESTION
MULTIPLE_SELECTION = exercises.MULTIPLE_SELECTION
SINGLE_SELECTION = exercises.SINGLE_SELECTION
FREE_RESPONSE = exercises.FREE_RESPONSE
PERSEUS_QUESTION = exercises.PERSEUS_QUESTION




# JSON READ/WRITE HELPERS
################################################################################

def read_tree_from_json(srcpath):
    """
    Load ricecooker json tree data from json file at `srcpath`.
    """
    with open(srcpath) as infile:
        json_tree = json.load(infile)
        if json_tree is None:
            raise ValueError('Could not find ricecooker json tree')
    return json_tree

def write_tree_to_json_tree(destpath, json_tree):
    """
    Save contents of `json_tree` (dict) to json file at `destpath`.
    """
    parent_dir, _ = os.path.split(destpath)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(destpath, 'w', encoding='utf8') as json_file:
        json.dump(json_tree, json_file, indent=2, ensure_ascii=False)


# CONSTRUCT CHANNEL FROM RICECOOKER JSON TREE
################################################################################

def get_channel_node_from_json(json_tree):
    """
    Build `ChannelNode` from json data provided in `json_tree`.
    """
    channel = ChannelNode(
        title=json_tree['title'],
        description=json_tree['description'],
        source_domain=json_tree['source_domain'],
        source_id=json_tree['source_id'],
        language=json_tree['language'],
        tagline=json_tree.get('tagline', None),
        thumbnail=json_tree.get('thumbnail', None),
    )
    return channel

def build_tree_from_json(parent_node, sourcetree):
    """
    Recusively parse nodes in the list `sourcetree` and add them as children
    to the `parent_node`. Usually called with `parent_node` being a `ChannelNode`.
    """
    EXPECTED_NODE_TYPES = [TOPIC_NODE, VIDEO_NODE, AUDIO_NODE, EXERCISE_NODE,
                           DOCUMENT_NODE, HTML5_NODE, SLIDESHOW_NODE]

    for source_node in sourcetree:
        kind = source_node['kind']
        if kind not in EXPECTED_NODE_TYPES:
            LOGGER.critical('Unexpected node kind found: ' + kind)
            raise NotImplementedError('Unexpected node kind found in json data.')

        if kind == TOPIC_NODE:
            child_node = nodes.TopicNode(
                source_id=source_node.get('source_id', None),
                title=source_node['title'],
                description=source_node.get('description'),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                # no role for topics (computed dynaically from descendants)
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                derive_thumbnail=source_node.get('derive_thumbnail', False),
                tags=source_node.get('tags'),
            )
            parent_node.add_child(child_node)
            source_tree_children = source_node.get('children', [])
            build_tree_from_json(child_node, source_tree_children)

        elif kind == VIDEO_NODE:
            child_node = nodes.VideoNode(
                source_id=source_node['source_id'],
                title=source_node['title'],
                description=source_node.get('description'),
                license=get_license(**source_node['license']),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                role=source_node.get('role', roles.LEARNER),
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                derive_thumbnail=source_node.get('derive_thumbnail', False),
                tags=source_node.get('tags'),
            )
            add_files(child_node, source_node.get('files') or [])
            parent_node.add_child(child_node)

        elif kind == AUDIO_NODE:
            child_node = nodes.AudioNode(
                source_id=source_node['source_id'],
                title=source_node['title'],
                description=source_node.get('description'),
                license=get_license(**source_node['license']),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                role=source_node.get('role', roles.LEARNER),
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                derive_thumbnail=source_node.get('derive_thumbnail', False),
                tags=source_node.get('tags'),
            )
            add_files(child_node, source_node.get('files') or [])
            parent_node.add_child(child_node)

        elif kind == EXERCISE_NODE:
            child_node = nodes.ExerciseNode(
                source_id=source_node['source_id'],
                title=source_node['title'],
                description=source_node.get('description'),
                license=get_license(**source_node['license']),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                role=source_node.get('role', roles.LEARNER),
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                derive_thumbnail=source_node.get('derive_thumbnail', False),  # not supported yet
                tags=source_node.get('tags'),
                exercise_data=source_node.get('exercise_data'),
                questions=[],
            )
            add_questions(child_node, source_node.get('questions') or [])
            parent_node.add_child(child_node)

        elif kind == DOCUMENT_NODE:
            child_node = nodes.DocumentNode(
                source_id=source_node['source_id'],
                title=source_node['title'],
                description=source_node.get('description'),
                license=get_license(**source_node['license']),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                role=source_node.get('role', roles.LEARNER),
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                tags=source_node.get('tags'),
            )
            add_files(child_node, source_node.get('files') or [])
            parent_node.add_child(child_node)

        elif kind == HTML5_NODE:
            child_node = nodes.HTML5AppNode(
                source_id=source_node['source_id'],
                title=source_node['title'],
                description=source_node.get('description'),
                license=get_license(**source_node['license']),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                role=source_node.get('role', roles.LEARNER),
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                derive_thumbnail=source_node.get('derive_thumbnail', False),
                tags=source_node.get('tags'),
            )
            add_files(child_node, source_node.get('files') or [])
            parent_node.add_child(child_node)

        elif kind == SLIDESHOW_NODE:
            child_node = nodes.SlideshowNode(
                source_id=source_node['source_id'],
                title=source_node['title'],
                description=source_node.get('description'),
                license=get_license(**source_node['license']),
                author=source_node.get('author'),
                aggregator=source_node.get('aggregator'),
                provider=source_node.get('provider'),
                role=source_node.get('role', roles.LEARNER),
                language=source_node.get('language'),
                thumbnail=source_node.get('thumbnail'),
                derive_thumbnail=source_node.get('derive_thumbnail', False),
                tags=source_node.get('tags')
            )
            add_files(child_node, source_node.get('files') or [])
            parent_node.add_child(child_node)

        # TODO: add support for H5P content kind

        else:
            LOGGER.critical('Encountered an unknown kind: ' + str(source_node))
            continue

    return parent_node


def add_files(node, file_list):
    EXPECTED_FILE_TYPES = [VIDEO_FILE, AUDIO_FILE, DOCUMENT_FILE, EPUB_FILE,
                           HTML5_FILE, THUMBNAIL_FILE, SUBTITLES_FILE, SLIDESHOW_IMAGE_FILE]

    for f in file_list:
        file_type = f.get('file_type')
        if file_type not in EXPECTED_FILE_TYPES:
            LOGGER.critical(file_type)
            raise NotImplementedError('Unexpected File type found in channel json.')

        path = f.get('path')  # path can be an URL or a local path (or None)

        # handle different types of files
        if file_type == VIDEO_FILE:
            # handle three types of video files
            if 'youtube_id' in f:
                video_file = files.YouTubeVideoFile(
                    youtube_id=f['youtube_id'],
                    download_settings=f.get('download_settings', None),
                    high_resolution=f.get('high_resolution', False),
                    maxheight=f.get('maxheight', None),
                    language=f.get('language', None),
                )
            elif 'web_url' in f:
                video_file = files.WebVideoFile(
                    web_url=f['web_url'],
                    download_settings=f.get('download_settings', None),
                    high_resolution=f.get('high_resolution', False),
                    maxheight=f.get('maxheight', None),
                    language=f.get('language', None),
                )
            else:
                video_file = files.VideoFile(
                    path=f['path'],
                    language=f.get('language', None),
                    ffmpeg_settings=f.get('ffmpeg_settings'),
                )
            node.add_file(video_file)


        elif file_type == AUDIO_FILE:
            node.add_file(
                files.AudioFile(
                    path=f['path'],
                    language=f.get('language', None)
                )
            )

        elif file_type == DOCUMENT_FILE:
            node.add_file(
                files.DocumentFile(
                    path=path,
                    language=f.get('language', None)
                )
            )

        elif file_type == EPUB_FILE:
            node.add_file(
                files.EPubFile(
                    path=path,
                    language=f.get('language', None)
                )
            )

        elif file_type == HTML5_FILE:
            node.add_file(
                files.HTMLZipFile(
                    path=path,
                    language=f.get('language', None)
                )
            )

        elif file_type == THUMBNAIL_FILE:
            if 'encoding' in f:
                node.add_file(
                    files.Base64ImageFile(
                        encoding=f['encoding'],
                    )
                )
            else:
                node.add_file(
                    files.ThumbnailFile(
                        path=path,
                        language=f.get('language', None),
                    )
                )

        elif file_type == SUBTITLES_FILE:
            if 'youtube_id' in f:
                node.add_file(
                    files.YouTubeSubtitleFile(
                        youtube_id=f['youtube_id'],
                        language=f['language']
                    )
                )
            else:
                keys = ['language', 'subtitlesformat']
                params = {'path': path}
                for key in keys:
                    if key in f:
                        params[key] = f[key]
                node.add_file(files.SubtitleFile(**params))

        elif file_type == SLIDESHOW_IMAGE_FILE:
            node.add_file(
                files.SlideImageFile(
                    path=path,
                    language=f.get('language', None),
                    caption=f.get('caption', ''),
                    descriptive_text=f.get('descriptive_text', '')
                )
            )

        else:
            raise UnknownFileTypeError('Unrecognized file type "{0}"'.format(f['path']))


def add_questions(exercise_node, question_list):
    EXPECTED_QUESTION_TYPES = [INPUT_QUESTION, MULTIPLE_SELECTION, SINGLE_SELECTION,
                               FREE_RESPONSE, PERSEUS_QUESTION]

    for q in question_list:
        question_type = q.get('question_type')
        if question_type not in EXPECTED_QUESTION_TYPES:
            LOGGER.critical(question_type)
            raise NotImplementedError('Unexpected question type found in channel json.')

        question_text = q.get('question')
        hints = q.get('hints')
        hints = hints if isinstance(hints, str) else [hint for hint in hints or []]

        if question_type == exercises.MULTIPLE_SELECTION:
            q_obj = questions.MultipleSelectQuestion(
                id=q['id'],
                question=question_text,
                correct_answers=[answer for answer in q['correct_answers']],
                all_answers=[answer for answer in q['all_answers']],
                hints=hints,
            )
            exercise_node.add_question(q_obj)

        elif question_type == exercises.SINGLE_SELECTION:
            q_obj = questions.SingleSelectQuestion(
                id=q['id'],
                question=question_text,
                correct_answer=q['correct_answer'],
                all_answers=[answer for answer in q['all_answers']],
                hints=hints,
            )
            exercise_node.add_question(q_obj)

        elif question_type == exercises.INPUT_QUESTION:
            q_obj = questions.InputQuestion(
                id=q['id'],
                question=question_text,
                answers=[answer for answer in q['answers']],
                hints=hints,
            )
            exercise_node.add_question(q_obj)

        elif question_type == exercises.PERSEUS_QUESTION:
            q_obj = questions.PerseusQuestion(
                id=q['id'],
                raw_data=q.get('item_data'),
                source_url=q.get('source_url') or 'https://www.khanacademy.org/',
            )
            exercise_node.add_question(q_obj)

        else:
            raise UnknownQuestionTypeError('Unrecognized question type {0}: accepted types are {1}'.format(question_type, [key for key, value in exercises.question_choices]))
