""" Tests for data validation and construction """

import copy
import json
import pytest
import uuid
import zipfile
from le_utils.constants import licenses, content_kinds, exercises
from ricecooker.classes.nodes import *
from ricecooker.classes.files import *
from ricecooker.classes.licenses import *
from ricecooker.classes.questions import *
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
def source_id():
    return "test-id"

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
def content_id(channel_domain_namespace, source_id):
    return uuid.uuid5(channel_domain_namespace, source_id)

@pytest.fixture
def node_id(channel_node_id, content_id):
    return uuid.uuid5(channel_node_id, content_id.hex)

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
        "ricecooker_version": __version__,
    }

@pytest.fixture
def channel(domain_namespace, channel_source_id, channel_data):
    return ChannelNode(channel_source_id, domain_namespace, channel_data["name"], description = channel_data['description'])

@pytest.fixture
def invalid_channel(domain_namespace, channel_source_id):
    channel = ChannelNode(channel_source_id, domain_namespace, "Channel")
    channel.source_id = None
    return channel


""" *********** TOPIC FIXTURES *********** """
@pytest.fixture
def title():
    return "Title"

@pytest.fixture
def license_id():
    return licenses.CC_BY

@pytest.fixture
def topic_kwargs_data():
    return {
        "description": "Description",
        "author": "Author",
        "extra_fields": {},
    }

@pytest.fixture
def kwargs_data(topic_kwargs_data):
    data = copy.deepcopy(topic_kwargs_data)
    data.update({"license_description": None, "copyright_holder": ""})
    return data

@pytest.fixture
def args_data(source_id, title, license_id):
    return source_id, title, license_id

@pytest.fixture
def base_data(node_id, content_id, channel_domain_namespace, source_id, topic_kwargs_data, title):
    data = copy.deepcopy(topic_kwargs_data)
    data.update({
        "title": title,
        "node_id": node_id.hex,
        "content_id": content_id.hex,
        "source_domain": channel_domain_namespace.hex,
        "source_id": source_id,
        "files" : [],
        "kind": None,
        "license": None,
        "license_description": None,
        "copyright_holder": "",
        "questions": [],
    })
    return data

@pytest.fixture
def topic_data(base_data):
    topic_data = copy.deepcopy(base_data)
    topic_data.update({ "kind": content_kinds.TOPIC })
    return topic_data

@pytest.fixture
def topic(source_id, channel, title, topic_kwargs_data):
    topic = TopicNode(source_id, title, **topic_kwargs_data)
    channel.add_child(topic)
    return topic


""" *********** CONTENT NODE FIXTURES *********** """
@pytest.fixture
def base_file_path():
    return "test/file/path"

@pytest.fixture
def contentnode_kwargs(kwargs_data):
    data = copy.deepcopy(kwargs_data)
    data.update({ "copyright_holder": "Copyright Holder" })
    return data

@pytest.fixture
def contentnode_base_data(base_data, contentnode_kwargs):
    data = copy.deepcopy(base_data)
    data.update({ "license": licenses.CC_BY})
    data.update(contentnode_kwargs)
    return data

@pytest.fixture
def contentnode_invalid_license(args_data):
    video = VideoNode(*args_data)
    video.license = None
    return video

@pytest.fixture
def contentnode_invalid_files(args_data, base_file_path):
    return VideoNode(*args_data)

@pytest.fixture
def contentnode_no_source_id(source_id, title):
    topic = TopicNode(source_id, title)
    topic.source_id = None
    return topic

@pytest.fixture
def topic_domain_namespace(channel_domain_namespace):
    return uuid.uuid5(channel_domain_namespace, 'alt-source-id')

@pytest.fixture
def topic_alt_content_id(topic_domain_namespace, source_id):
    return uuid.uuid5(topic_domain_namespace, source_id)

@pytest.fixture
def topic_alt_node_id(channel_node_id, topic_alt_content_id):
    return uuid.uuid5(channel_node_id, topic_alt_content_id.hex)

@pytest.fixture
def topic_alternative_domain(source_id, topic_domain_namespace, title, channel):
    topic = TopicNode(source_id, title, domain_ns=topic_domain_namespace)
    channel.add_child(topic)
    return topic

@pytest.fixture
def video_file(base_file_path):
    return VideoFile(base_file_path)

@pytest.fixture
def audio_file(base_file_path):
    return AudioFile(base_file_path)

@pytest.fixture
def document_file(base_file_path):
    return DocumentFile(base_file_path)

@pytest.fixture
def html_file():
    if not os.path.exists("tests/testcontent/testhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('index.html', '<div></div>')

    return HTMLZipFile("tests/testcontent/testhtml.zip")


""" *********** VIDEO FIXTURES *********** """
@pytest.fixture
def video_data(contentnode_base_data, video_file):
    video_data = copy.deepcopy(contentnode_base_data)
    video_data.update({ "kind": content_kinds.VIDEO, "files":[video_file], "extra_fields": "{}"})
    return video_data

@pytest.fixture
def video(video_file, args_data, contentnode_kwargs, channel):
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(video_file)
    channel.add_child(video)
    return video

@pytest.fixture
def video_invalid_files(args_data, contentnode_kwargs, document_file):
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(document_file)
    return video


""" *********** AUDIO FIXTURES *********** """
@pytest.fixture
def audio_data(contentnode_base_data, audio_file):
    audio_data = copy.deepcopy(contentnode_base_data)
    audio_data.update({ "kind": content_kinds.AUDIO, "files":[audio_file], "extra_fields": "{}"})
    return audio_data

@pytest.fixture
def audio(audio_file, args_data, contentnode_kwargs, channel):
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(audio_file)
    channel.add_child(audio)
    return audio

@pytest.fixture
def audio_invalid_files(args_data, contentnode_kwargs, document_file):
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(document_file)
    return audio


""" *********** DOCUMENT FIXTURES *********** """
@pytest.fixture
def document_data(contentnode_base_data, document_file):
    document_data = copy.deepcopy(contentnode_base_data)
    document_data.update({ "kind": content_kinds.DOCUMENT, "files":[document_file], "extra_fields": "{}"})
    return document_data

@pytest.fixture
def document(document_file, args_data, contentnode_kwargs, channel):
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(document_file)
    channel.add_child(document)
    return document

@pytest.fixture
def document_invalid_files(args_data, contentnode_kwargs, audio_file):
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(audio_file)
    return document


""" *********** HTML FIXTURES *********** """
@pytest.fixture
def html_data(contentnode_base_data, html_file):
    html_data = copy.deepcopy(contentnode_base_data)
    html_data.update({ "kind": content_kinds.HTML5, "files":[html_file], "extra_fields": "{}"})
    return html_data

@pytest.fixture
def html(html_file, args_data, contentnode_kwargs, channel):
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(html_file)
    channel.add_child(html)
    return html


@pytest.fixture
def html_invalid_file():
    if not os.path.exists("tests/testcontent/testinvalidhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testinvalidhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("notindex.html", '<div></div>')
    return HTMLZipFile("tests/testcontent/testinvalidhtml.zip")


@pytest.fixture
def html_invalid_files(args_data, contentnode_kwargs, document_file):
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(document_file)
    return html

@pytest.fixture
def html_invalid_zip(args_data, contentnode_kwargs, html_invalid_file):
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
def exercise_data(contentnode_base_data, mastery_model, exercise_question):
    exercise_data = copy.deepcopy(contentnode_base_data)
    exercise_data.update({ "kind": content_kinds.EXERCISE, "questions":[exercise_question], "extra_fields": json.dumps(mastery_model)})
    return exercise_data

@pytest.fixture
def exercise_kwargs(contentnode_kwargs, mastery_model):
    kwargs = copy.deepcopy(contentnode_kwargs)
    kwargs.pop("extra_fields")
    kwargs.update({'exercise_data': mastery_model})
    return kwargs

@pytest.fixture
def exercise(exercise_question, args_data, exercise_kwargs, channel, mastery_model):
    exercise = ExerciseNode(*args_data, **exercise_kwargs)
    exercise.add_question(exercise_question)
    channel.add_child(exercise)
    return exercise

@pytest.fixture
def exercise_invalid_question(args_data, exercise_kwargs):
    exercise = ExerciseNode(*args_data, **exercise_kwargs)
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
    pytest.raises(InvalidNodeException, html_invalid_zip.validate)
    assert exercise.validate(), "Valid html content should pass validation"
    pytest.raises(InvalidQuestionException, exercise_invalid_question.validate)

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
    assert video.files == video_data.pop('files'), "Video files do not match"
    for key, _ in video_data.items():
        assert key in video_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in video_dict.items():
        assert value == video_data.get(key), "Mismatched {}: {} != {}".format(key, value, video_data[key])

def test_audio_to_dict(audio, audio_data):
    audio_dict = audio.to_dict()
    audio_dict.pop('files')
    assert audio.files == audio_data.pop('files'), "Audio files do not match"
    for key, _ in audio_data.items():
        assert key in audio_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in audio_dict.items():
        assert value == audio_data.get(key), "Mismatched {}: {} != {}".format(key, value, audio_data[key])

def test_document_to_dict(document, document_data):
    document_dict = document.to_dict()
    document_dict.pop('files')
    assert document.files == document_data.pop('files'), "Document files do not match"
    for key, _ in document_data.items():
        assert key in document_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in document_dict.items():
        assert value == document_data.get(key), "Mismatched {}: {} != {}".format(key, value, document_data[key])

def test_html_to_dict(html, html_data):
    html_dict = html.to_dict()
    html_dict.pop('files')
    assert html.files == html_data.pop('files'), "HTML files do not match"
    for key, _ in html_data.items():
        assert key in html_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in html_dict.items():
        assert value == html_data.get(key), "Mismatched {}: {} != {}".format(key, value, html_data[key])

def test_exercise_to_dict(exercise, exercise_data):
    exercise_dict = exercise.to_dict()
    exercise_dict.pop('questions')
    assert exercise.questions == exercise_data.pop('questions'), "Exercise questions do not match"
    for key, _ in exercise_data.items():
        assert key in exercise_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in exercise_dict.items():
        assert value == exercise_data.get(key), "Mismatched {}: {} != {}".format(key, value, exercise_data[key])
