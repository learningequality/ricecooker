""" Tests for data validation and construction """

import copy
import json
import os
import pytest
import string
import uuid
import zipfile

from le_utils.constants import licenses, content_kinds, exercises
from ricecooker.classes.nodes import ChannelNode, TopicNode, VideoNode, AudioNode, DocumentNode, HTML5AppNode, ExerciseNode
from ricecooker.classes.files import VideoFile, AudioFile, DocumentFile, HTMLZipFile
from ricecooker.classes.questions import SingleSelectQuestion, InputQuestion
from ricecooker.exceptions import InvalidNodeException, InvalidQuestionException
from ricecooker.__init__ import __version__



""" *********** CHANNEL FIXTURES *********** """

@pytest.fixture
def domain_namespace():
    return "testing.learningequality.org"

@pytest.fixture
def channel_source_id():
    return "channel-id"

@pytest.fixture
def channel_domain_namespace(domain_namespace):
    return uuid.uuid5(uuid.NAMESPACE_DNS, domain_namespace)

@pytest.fixture
def channel_node_id(channel_domain_namespace, channel_source_id):
    return uuid.uuid5(channel_domain_namespace, channel_source_id)

@pytest.fixture
def channel_content_id(channel_domain_namespace, channel_node_id):
    return uuid.uuid5(channel_domain_namespace, channel_node_id.hex)

@pytest.fixture
def channel_data(channel_node_id, channel_content_id, domain_namespace, channel_source_id):
    return {
        "id": channel_node_id.hex,
        "name": "Channel",
        "thumbnail": None,
        "description": "Channel description",
        "license": None,
        "source_domain": domain_namespace,
        "source_id": channel_source_id,
        "language": "en",
        "ricecooker_version": __version__,
    }

@pytest.fixture
def channel(domain_namespace, channel_source_id, channel_data):
    channel = ChannelNode(
        channel_source_id,
        domain_namespace,
        title=channel_data['name'],
        description=channel_data['description'],
        language=channel_data['language']
    )
    return channel

@pytest.fixture
def invalid_channel(channel_source_id, domain_namespace):
    channel = ChannelNode(
        channel_source_id,
        domain_namespace,
        title='Invalid Channel'
    )
    channel.source_id = None
    return channel




""" *********** ID, ARGS, AND KWARGS FIXTURE HELPERS *********** """

@pytest.fixture
def base_data(channel_domain_namespace, title):
    """
    The dictionary returned by this function resembles outpout of `to_dict` method.
    """
    return {
        "kind": None,
        "title": title,
        "description": "Description",
        "author": "Author",
        "source_domain": channel_domain_namespace.hex,
        "files" : [],
        "questions": [],
        "extra_fields": "{}",  # because Ricecookr uses `json.dumps` for this field
        "license": None,
        "copyright_holder": "",
        "license_description": None,
    }


def genrate_random_ids(channel_domain_namespace, channel_node_id):
    """
    Helper function to ensure all ContentNodes in test channel have unique `source_id`s.
    """
    source_id = uuid.uuid4().hex
    content_id = uuid.uuid5(channel_domain_namespace, source_id)
    node_id = uuid.uuid5(channel_node_id, content_id.hex)
    ids_dict = dict(
        source_id=source_id,
        content_id=content_id.hex,
        node_id=node_id.hex,
    )
    return ids_dict




""" *********** TOPIC FIXTURES *********** """

def get_topic_node_args(node_data):
    """
    Returns (source_id, title) from node_data dictionary.
    """
    node_data = copy.deepcopy(node_data)
    source_id = node_data.pop('source_id')
    title = node_data.pop('title')
    license = node_data.pop('license')
    return source_id, title

def get_topic_node_kwargs_data(node_data):
    """
    Returns all keywords data other than source_id, title, and license.
    """
    node_data = copy.deepcopy(node_data)
    del node_data['source_id']
    del node_data['title']
    # the following attributes will appear in `to_dict` method, but we don't need
    # to pass them in when creating a TopicNode
    del node_data['content_id']
    del node_data['node_id']
    del node_data['kind']
    del node_data['source_domain']
    del node_data['questions']
    del node_data['license']
    del node_data['license_description']
    del node_data['copyright_holder']
    return node_data


@pytest.fixture
def title():
    return "Title"


@pytest.fixture
def topic_data(base_data, channel_domain_namespace, channel_node_id):
    topic_data = copy.deepcopy(base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    topic_data.update(ids_dict)
    topic_data.update({ "kind": content_kinds.TOPIC,
                        "extra_fields": {} })
    return topic_data

@pytest.fixture
def topic(channel, title, topic_data):
    args_data = get_topic_node_args(topic_data)
    topic_kwargs = get_topic_node_kwargs_data(topic_data)
    topic = TopicNode(*args_data, **topic_kwargs)
    channel.add_child(topic)
    return topic





""" *********** CONTENT NODE FIXTURES *********** """


@pytest.fixture
def contentnode_base_data(base_data):
    """
    Shared data for all ContentNode fixtures.
    """
    data = copy.deepcopy(base_data)
    data.update({ "license": licenses.CC_BY,
                  "copyright_holder": "Copyright Holder",
                  "license_description": None})
    return data


def get_content_node_args(node_data):
    """
    Returns (source_id, title, license) from node_data dictionary.
    """
    node_data = copy.deepcopy(node_data)
    source_id = node_data.pop('source_id')
    title = node_data.pop('title')
    license = node_data.pop('license')
    return source_id, title, license


def get_content_node_kwargs(node_data):
    """
    Returns all keywords data other than source_id, title, and license.
    """
    node_data = copy.deepcopy(node_data)
    del node_data['source_id']
    del node_data['title']
    del node_data['license']
    # below are vars from internal representation
    del node_data['content_id']
    del node_data['node_id']
    del node_data['kind']
    del node_data['source_domain']
    del node_data['questions']
    node_data['extra_fields'] = {}
    return node_data


@pytest.fixture
def base_file_path():
    return "test/file/path"

@pytest.fixture
def contentnode_invalid_license(video):
    video = copy.deepcopy(video)
    video.license = None
    return video

@pytest.fixture
def contentnode_invalid_files(video):
    video = copy.deepcopy(video)
    video.files = []
    return video

@pytest.fixture
def contentnode_no_source_id(title):
    topic = TopicNode('some source id', title)
    topic.source_id = None
    return topic





""" *********** VIDEO FIXTURES *********** """

@pytest.fixture
def video_file(base_file_path):
    return VideoFile(base_file_path)

@pytest.fixture
def video_data(contentnode_base_data, channel_domain_namespace, channel_node_id):
    video_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    video_data.update(ids_dict)
    video_data.update({ "kind": content_kinds.VIDEO })
    return video_data

@pytest.fixture
def video(video_file, video_data, channel):
    args_data = get_content_node_args(video_data)
    contentnode_kwargs = get_content_node_kwargs(video_data)
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(video_file)
    channel.add_child(video)
    video_data['files'].append(video_file)  # save it so we can compare later
    return video

@pytest.fixture
def video_invalid_files(video_data, document_file):
    args_data = get_content_node_args(video_data)
    contentnode_kwargs = get_content_node_kwargs(video_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(document_file)
    return video



""" *********** AUDIO FIXTURES *********** """

@pytest.fixture
def audio_file(base_file_path):
    return AudioFile(base_file_path)

@pytest.fixture
def audio_data(contentnode_base_data, audio_file, channel_domain_namespace, channel_node_id):
    audio_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    audio_data.update(ids_dict)
    audio_data.update({ "kind": content_kinds.AUDIO })
    return audio_data

@pytest.fixture
def audio(audio_file, audio_data, channel):
    args_data = get_content_node_args(audio_data)
    contentnode_kwargs = get_content_node_kwargs(audio_data)
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(audio_file)
    channel.add_child(audio)
    audio_data['files'].append(audio_file)  # save it so we can compare later
    return audio

@pytest.fixture
def audio_invalid_files(audio_data, document_file):
    args_data = get_content_node_args(audio_data)
    contentnode_kwargs = get_content_node_kwargs(audio_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(document_file)
    return audio


""" *********** DOCUMENT FIXTURES *********** """

@pytest.fixture
def document_file(base_file_path):
    return DocumentFile(base_file_path)

@pytest.fixture
def document_data(contentnode_base_data, document_file, channel_domain_namespace, channel_node_id):
    document_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    document_data.update(ids_dict)
    document_data.update({ "kind": content_kinds.DOCUMENT })
    return document_data

@pytest.fixture
def document(document_file, document_data, channel):
    args_data = get_content_node_args(document_data)
    contentnode_kwargs = get_content_node_kwargs(document_data)
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(document_file)
    channel.add_child(document)
    document_data['files'].append(document_file)  # save it so we can compare later
    return document

@pytest.fixture
def document_invalid_files(document_data, audio_file):
    args_data = get_content_node_args(document_data)
    contentnode_kwargs = get_content_node_kwargs(document_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(audio_file)
    return document



""" *********** HTML FIXTURES *********** """

@pytest.fixture
def html_file():
    if not os.path.exists("tests/testcontent/testhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('index.html', '<div></div>')
    return HTMLZipFile("tests/testcontent/testhtml.zip")

@pytest.fixture
def html_data(contentnode_base_data, html_file, channel_domain_namespace, channel_node_id):
    html_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    html_data.update(ids_dict)
    html_data.update({ "kind": content_kinds.HTML5 })
    return html_data

@pytest.fixture
def html(html_file, html_data, channel):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(html_file)
    channel.add_child(html)
    html_data['files'].append(html_file)  # save it so we can compare later
    return html


@pytest.fixture
def html_invalid_files(html_data, document_file):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(document_file)
    return html


@pytest.fixture
def html_invalid_file():
    if not os.path.exists("tests/testcontent/testinvalidhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testinvalidhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("notindex.html", '<div></div>')
    return HTMLZipFile("tests/testcontent/testinvalidhtml.zip")

@pytest.fixture
def html_invalid_zip(html_data, html_invalid_file):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(html_invalid_file)
    return html


""" *********** EXERCISE FIXTURES *********** """

@pytest.fixture
def exercise_question():
    return SingleSelectQuestion("question_1", "Question", "Answer", ["Answer"])

@pytest.fixture
def mastery_model():
    return {'mastery_model': exercises.M_OF_N, 'randomize': True, 'm': 1, 'n': 1}

@pytest.fixture
def exercise_data(contentnode_base_data, mastery_model, exercise_question, channel_domain_namespace, channel_node_id):
    exercise_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    exercise_data.update(ids_dict)
    exercise_data.update({ "kind": content_kinds.EXERCISE,
                           "questions":[],
                           "exercise_data": mastery_model})
    return exercise_data

@pytest.fixture
def exercise(exercise_question, exercise_data, channel):
    args_data = get_content_node_args(exercise_data)
    contentnode_kwargs = get_content_node_kwargs(exercise_data)
    del contentnode_kwargs['extra_fields']
    mastery_model_dict = contentnode_kwargs['exercise_data']
    exercise = ExerciseNode(*args_data, **contentnode_kwargs)
    exercise.add_question(exercise_question)
    channel.add_child(exercise)
    exercise_data['questions'] = [exercise_question]
    exercise_data['extra_fields'] = mastery_model_dict
    del exercise_data['exercise_data']
    return exercise

@pytest.fixture
def exercise_invalid_question(exercise):
    exercise = copy.deepcopy(exercise)
    exercise.add_question(InputQuestion("question_2", "Question 2", ["Answer"]))
    return exercise




""" *********** CHANNEL TESTS *********** """

def test_init(channel, topic, video, audio, document, html, exercise):
    # Channel init
    assert channel, "Channel was not created"
    pytest.raises(TypeError, ChannelNode)

    # Topic init
    assert topic, "Topic node was not created"
    assert topic.kind == content_kinds.TOPIC, "Topic nodes must have TOPIC kind"

    # Content node init
    assert video, "Video was not created"
    assert audio, "Audio was not created"
    assert document, "Document was not created"
    assert html, "HTML was not created"
    assert exercise, "Exercise was not created"

def test_validate(channel, invalid_channel, topic, contentnode_invalid_license, contentnode_invalid_files, contentnode_no_source_id, video, video_invalid_files,
    audio, audio_invalid_files, document, document_invalid_files, html, html_invalid_files, html_invalid_zip, exercise, exercise_invalid_question):
    assert channel.validate(), "Valid channel should pass validation"
    pytest.raises(InvalidNodeException, invalid_channel.validate)
    assert topic.validate(), "Valid topics should pass validation"

    # Content node validation
    pytest.raises(InvalidNodeException, contentnode_invalid_license.validate)
    pytest.raises(InvalidNodeException, contentnode_no_source_id.validate)
    pytest.raises(InvalidNodeException, contentnode_invalid_files.validate)
    assert video.validate(), "Valid videos should pass validation"
    pytest.raises(InvalidNodeException, video_invalid_files.validate)
    assert audio.validate(), "Valid audio content should pass validation"
    pytest.raises(InvalidNodeException, audio_invalid_files.validate)
    assert document.validate(), "Valid document content should pass validation"
    pytest.raises(InvalidNodeException, document_invalid_files.validate)
    assert html.validate(), "Valid html content should pass validation"
    pytest.raises(InvalidNodeException, html_invalid_files.validate)
    # pytest.raises(InvalidNodeException, html_invalid_zip.validate)  # TODO: implement index.html checking logic
    assert exercise.validate(), "Valid html content should pass validation"
    pytest.raises(InvalidQuestionException, exercise_invalid_question.validate)




""" *********** ALT DOMAIN TESTS *********** """

@pytest.fixture
def topic_domain_namespace(channel_domain_namespace):
    return uuid.uuid5(channel_domain_namespace, 'alt-source-id')

@pytest.fixture
def topic_alt_content_id(topic_domain_namespace):
    return uuid.uuid5(topic_domain_namespace, 'test-alt')

@pytest.fixture
def topic_alt_node_id(channel_node_id, topic_alt_content_id):
    return uuid.uuid5(channel_node_id, topic_alt_content_id.hex)

@pytest.fixture
def topic_alternative_domain(topic_domain_namespace, title, channel):
    topic = TopicNode('test-alt', title, domain_ns=topic_domain_namespace)
    channel.add_child(topic)
    return topic

def test_alternative_domain_namespace(topic_alternative_domain, topic_domain_namespace, topic_alt_node_id, topic_alt_content_id):
    assert topic_alternative_domain.get_domain_namespace() == topic_domain_namespace, "Topic domain should be {}".format(topic_domain_namespace)
    assert topic_alternative_domain.get_content_id() == topic_alt_content_id, "Topic content id should be {}".format(topic_alt_content_id)
    assert topic_alternative_domain.get_node_id() == topic_alt_node_id, "Topic node id should be {}".format(topic_alt_node_id)




""" *********** TO_DICT TESTS *********** """

def test_channel_to_dict(channel, channel_data):
    channel_dict = channel.to_dict().items()
    assert len(channel_dict) == len(channel_data.items()), "Channel to_dict does not have the expected number of fields"
    for key, value in channel_dict:
        assert value == channel_data[key], "Mismatched {}: {} != {}".format(key, value, channel_data[key])

def test_topic_to_dict(topic, topic_data):
    topic_dict = topic.to_dict()
    for key, _ in topic_data.items():
        assert key in topic_dict, "Key {} is not found in topic to_dict method".format(key)
    for key, value in topic_dict.items():
        assert value == topic_data.get(key), "Mismatched {}: {} != {}".format(key, value, topic_data[key])

def test_video_to_dict(video, video_data):
    video_dict = video.to_dict()
    video_dict.pop('files')
    expected_files = video_data.pop('files')
    assert video.files == expected_files, "Video files do not match"
    for key, _ in video_data.items():
        assert key in video_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in video_dict.items():
        assert value == video_data.get(key), "Mismatched {}: {} != {}".format(key, value, video_data[key])

def test_audio_to_dict(audio, audio_data):
    audio_dict = audio.to_dict()
    audio_dict.pop('files')
    expected_files = audio_data.pop('files')
    print('zzz', audio.files, expected_files)
    assert audio.files == expected_files, "Audio files do not match"
    for key, _ in audio_data.items():
        assert key in audio_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in audio_dict.items():
        assert value == audio_data.get(key), "Mismatched {}: {} != {}".format(key, value, audio_data[key])

def test_document_to_dict(document, document_data):
    document_dict = document.to_dict()
    document_dict.pop('files')
    expected_files = document_data.pop('files')
    assert document.files == expected_files, "Document files do not match"
    for key, _ in document_data.items():
        assert key in document_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in document_dict.items():
        assert value == document_data.get(key), "Mismatched {}: {} != {}".format(key, value, document_data[key])

def test_html_to_dict(html, html_data):
    html_dict = html.to_dict()
    html_dict.pop('files')
    expected_files = html_data.pop('files')
    assert html.files == expected_files, "HTML files do not match"
    for key, _ in html_data.items():
        assert key in html_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in html_dict.items():
        assert value == html_data.get(key), "Mismatched {}: {} != {}".format(key, value, html_data[key])

def test_exercise_to_dict(exercise, exercise_data):
    exercise_dict = exercise.to_dict()
    exercise_dict.pop('questions')
    the_exercise_data = json.loads(exercise_dict['extra_fields'])
    assert the_exercise_data == exercise_data['extra_fields'], 'Different extra_fields found'
    del exercise_dict['extra_fields']
    del exercise_data['extra_fields']
    assert exercise.questions == exercise_data.pop('questions'), "Exercise questions do not match"
    for key, _ in exercise_data.items():
        assert key in exercise_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in exercise_dict.items():
        assert value == exercise_data.get(key), "Mismatched {}: {} != {}".format(key, value, exercise_data[key])
