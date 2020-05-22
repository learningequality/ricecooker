""" Tests for data validation and construction """

import json
import os
import pytest
import uuid

from le_utils.constants import licenses, content_kinds, exercises, roles
from ricecooker.classes.nodes import ChannelNode, TopicNode
from ricecooker.exceptions import InvalidNodeException, InvalidQuestionException


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
    topic_data['extra_fields'] = json.dumps(topic_data['extra_fields'])
    for key, _ in topic_data.items():
        assert key in topic_dict, "Key {} is not found in topic to_dict method".format(key)
    for key, value in topic_dict.items():
        assert value == topic_data.get(key), "Mismatched {}: {} != {}".format(key, value, topic_data[key])

def test_video_to_dict(video, video_data):
    video_dict = video.to_dict()
    video_dict.pop('files')
    expected_files = video_data.pop('files')
    video_data['extra_fields'] = json.dumps(video_data['extra_fields'])
    assert video.files == expected_files, "Video files do not match"
    for key, _ in video_data.items():
        assert key in video_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in video_dict.items():
        assert value == video_data.get(key), "Mismatched {}: {} != {}".format(key, value, video_data[key])

def test_audio_to_dict(audio, audio_data):
    audio_dict = audio.to_dict()
    audio_dict.pop('files')
    expected_files = audio_data.pop('files')
    audio_data['extra_fields'] = json.dumps(audio_data['extra_fields'])
    assert audio.files == expected_files, "Audio files do not match"
    for key, _ in audio_data.items():
        assert key in audio_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in audio_dict.items():
        assert value == audio_data.get(key), "Mismatched {}: {} != {}".format(key, value, audio_data[key])

def test_document_to_dict(document, document_data):
    document_dict = document.to_dict()
    document_dict.pop('files')
    expected_files = document_data.pop('files')
    document_data['extra_fields'] = json.dumps(document_data['extra_fields'])
    assert document.files == expected_files, "Document files do not match"
    for key, _ in document_data.items():
        assert key in document_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in document_dict.items():
        assert value == document_data.get(key), "Mismatched {}: {} != {}".format(key, value, document_data[key])

def test_html_to_dict(html, html_data):
    html_dict = html.to_dict()
    html_dict.pop('files')
    expected_files = html_data.pop('files')
    html_data['extra_fields'] = json.dumps(html_data['extra_fields'])
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

def test_slideshow_to_dict(slideshow, slideshow_data):
    slideshow_dict = slideshow.to_dict()
    extra_fields = json.loads(slideshow_dict['extra_fields'])
    assert len(extra_fields['slideshow_data']) == 10, 'wrong num slides'
    expected_field_keys = { 'caption', 'descriptive_text', 'checksum', 'sort_order', 'extension'}
    assert all([set(sd.keys()) == expected_field_keys for sd in extra_fields['slideshow_data']]), 'extra_fields is missing expected fields'
    del slideshow_data['extra_fields']
    del slideshow_dict['extra_fields']
    #
    expected_files = slideshow_data.pop('files')
    slideshow_dict.pop('files')
    assert slideshow.files == expected_files, "slideshow_images do not match"
    for key, _ in slideshow_data.items():
        assert key in slideshow_dict, "Key {} is not found in to_dict method".format(key)
    for key, value in slideshow_dict.items():
         assert value == slideshow_data.get(key), "Mismatched {}: {} != {}".format(key, value, slideshow_data[key])

