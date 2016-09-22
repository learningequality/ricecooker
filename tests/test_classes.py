import pytest
import uuid
import tempfile
from fle_utils import constants
import base64
from ricecooker.classes import *


""" *********** CHANNEL FIXTURES *********** """
@pytest.fixture
def channel_id():
    return "sample-channel"

@pytest.fixture
def channel_domain():
    return "learningequality.org"

@pytest.fixture
def channel_internal_domain(channel_domain):
    return uuid.uuid5(uuid.NAMESPACE_DNS, channel_domain)

@pytest.fixture
def channel_uuid(channel_id):
    return uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, channel_id).hex)

@pytest.fixture
def channel_data(channel_id, channel_domain):
    return {
    	"domain" : channel_domain,
        "channel_id" : channel_id,
        "title" : "Sample Channel",
    }

@pytest.fixture
def channel(channel_data):
    return Channel(
		domain=channel_data['domain'],
		channel_id=channel_data['channel_id'],
		title=channel_data['title'],
	)

@pytest.fixture
def channel_json(channel, channel_data, channel_uuid):
    return {
    	"name" : channel_data['title'],
        "id" : channel_uuid.hex,
        "thumbnail" : channel.thumbnail,
        "has_changed" : True,
        "description" : channel.description,
    }

@pytest.fixture
def root_content_id(channel, channel_internal_domain):
	return uuid.uuid5(channel_internal_domain, channel.id.hex)

@pytest.fixture
def root_node_id(channel, root_content_id):
	return uuid.uuid5(channel.id, root_content_id.hex)



""" *********** TOPIC FIXTURES *********** """
@pytest.fixture
def topic_id():
    return "topic-id"

@pytest.fixture
def topic_content_id(channel_internal_domain, topic_id):
    return uuid.uuid5(channel_internal_domain, topic_id)

@pytest.fixture
def topic_node_id(root_node_id, topic_content_id):
    return uuid.uuid5(root_node_id, topic_content_id.hex)

@pytest.fixture
def topic_data(topic_id):
    return {
    	"title": "topic node test",
    	"description": None,
        "id" : topic_id,
        "author": None,
    }

@pytest.fixture
def topic(topic_data, channel_internal_domain, root_node_id):
    node = Topic(
        id=topic_data['id'],
        description=topic_data['description'],
        title=topic_data['title'],
        author=topic_data['author']
    )
    node.set_ids(channel_internal_domain, root_node_id)
    return node

@pytest.fixture
def topic_json(topic_data, topic_content_id, topic_node_id):
    return {
        "id" : topic_data['id'],
        "title": topic_data['title'],
        "description": "",
        "node_id": topic_node_id.hex,
        "content_id": topic_content_id.hex,
        "author": "",
        "files": [],
        "kind": constants.CK_TOPIC,
        "license": None,
    }

""" *********** VIDEO FIXTURES *********** """
@pytest.fixture
def video_id():
    return "video-id"

@pytest.fixture
def video_content_id(channel_internal_domain, video_id):
    return uuid.uuid5(channel_internal_domain, video_id)

@pytest.fixture
def video_node_id(topic_node_id, video_content_id):
    return uuid.uuid5(topic_node_id, video_content_id.hex)

@pytest.fixture
def video_data(video_id):
    return {
    	"title": "video node test",
    	"description": None,
        "id" : video_id,
        "author": None,
        "license": constants.L_PD,
    }

@pytest.fixture
def video(video_data, channel_internal_domain, topic_node_id):
    node = Video(
		id=video_data['id'],
		description=video_data['description'],
		title=video_data['title'],
		author=video_data['author'],
		transcode_to_lower_resolutions=True,
		derive_thumbnail=True,
		license=video_data['license'],
	)
    node.set_ids(channel_internal_domain, topic_node_id)
    return node

@pytest.fixture
def video_json(video_data, video_content_id, video_node_id):
    return {
        "id" : video_data['id'],
        "title": video_data['title'],
        "description": "",
        "node_id": video_node_id.hex,
        "content_id": video_content_id.hex,
        "author": "",
        "children": [],
        "files": [],
        "kind": constants.CK_VIDEO,
        "license": video_data['license'],
    }



""" *********** AUDIO FIXTURES *********** """
@pytest.fixture
def audio_id():
    return "audio-id"

@pytest.fixture
def audio_content_id(channel_internal_domain, audio_id):
    return uuid.uuid5(channel_internal_domain, audio_id)

@pytest.fixture
def audio_node_id(topic_node_id, audio_content_id):
    return uuid.uuid5(topic_node_id, audio_content_id.hex)

@pytest.fixture
def audio_data(audio_id):
    return {
    	"title": "audio node test",
    	"description": None,
        "id" : audio_id,
        "author": None,
        "license": constants.L_PD,
    }

@pytest.fixture
def audio(audio_data, channel_internal_domain, topic_node_id):
    node = Audio(
		id=audio_data['id'],
		description=audio_data['description'],
		title=audio_data['title'],
		author=audio_data['author'],
		license=audio_data['license'],
	)
    node.set_ids(channel_internal_domain, topic_node_id)
    return node

@pytest.fixture
def audio_json(audio_data, audio_content_id, audio_node_id):
    return {
        "id" : audio_data['id'],
        "title": audio_data['title'],
        "description": "",
        "node_id": audio_node_id.hex,
        "content_id": audio_content_id.hex,
        "author": "",
        "children": [],
        "files": [],
        "kind": constants.CK_AUDIO,
        "license": audio_data['license'],
    }



""" *********** DOCUMENT FIXTURES *********** """
@pytest.fixture
def document_id():
    return "document-id"

@pytest.fixture
def document_content_id(channel_internal_domain, document_id):
    return uuid.uuid5(channel_internal_domain, document_id)

@pytest.fixture
def document_node_id(root_node_id, document_content_id):
    return uuid.uuid5(root_node_id, document_content_id.hex)

@pytest.fixture
def document_data(document_id):
    return {
    	"title": "document node test",
    	"description": None,
        "id" : document_id,
        "author": None,
        "license": constants.L_PD,
    }

@pytest.fixture
def document(document_data, channel_internal_domain, root_node_id):
    node = Document(
		id=document_data['id'],
		description=document_data['description'],
		title=document_data['title'],
		author=document_data['author'],
		license=document_data['license'],
	)
    node.set_ids(channel_internal_domain, root_node_id)
    return node

@pytest.fixture
def document_json(document_data, document_content_id, document_node_id):
    return {
        "id" : document_data['id'],
        "title": document_data['title'],
        "description": "",
        "node_id": document_node_id.hex,
        "content_id": document_content_id.hex,
        "author": "",
        "children": [],
        "files": [],
        "kind": constants.CK_DOCUMENT,
        "license": document_data['license'],
    }



""" *********** EXERCISE FIXTURES *********** """
@pytest.fixture
def exercise_id():
    return "exercise-id"

@pytest.fixture
def exercise_content_id(channel_internal_domain, exercise_id):
    return uuid.uuid5(channel_internal_domain, exercise_id)

@pytest.fixture
def exercise_node_id(topic_node_id, exercise_content_id):
    return uuid.uuid5(topic_node_id, exercise_content_id.hex)

@pytest.fixture
def exercise_data(exercise_id):
    return {
    	"title": "exercise node test",
    	"description": None,
        "id" : exercise_id,
        "author": None,
        "license": constants.L_PD,
    }

@pytest.fixture
def exercise(exercise_data, channel_internal_domain, topic_node_id):
    node = Exercise(
		id=exercise_data['id'],
		description=exercise_data['description'],
		title=exercise_data['title'],
		author=exercise_data['author'],
		license=exercise_data['license'],
	)
    node.set_ids(channel_internal_domain, topic_node_id)
    return node

@pytest.fixture
def exercise_json(exercise_data, exercise_content_id, exercise_node_id):
    return {
        "id" : exercise_data['id'],
        "title": exercise_data['title'],
        "description": "",
        "node_id": exercise_node_id.hex,
        "content_id": exercise_content_id.hex,
        "author": "",
        "children": [],
        "files": [],
        "kind": constants.CK_EXERCISE,
        "license": exercise_data['license'],
    }



""" *********** CHANNEL TESTS *********** """
def test_channel_created(channel):
	assert channel is not None

def test_channel_data(channel, channel_data, channel_uuid):
	assert channel.domain == channel_data['domain']
	assert channel.name == channel_data['title']
	assert channel.id == channel_uuid

def test_channel_to_dict(channel, channel_json):
    assert channel.id.hex == channel_json['id']
    assert channel.name == channel_json['name']
    assert channel_json['description'] == None
    assert channel_json['has_changed'] == True



""" *********** TOPIC TESTS *********** """
def test_topic_created(topic):
	assert topic is not None

def test_topic_data(topic, topic_data):
	assert topic.id == topic_data['id']
	assert topic.title == topic_data['title']
	assert topic.description == topic_data['description']
	assert topic.author == topic_data['author']
	assert topic.kind == constants.CK_TOPIC

def test_topic_ids(topic, topic_content_id, topic_node_id):
	assert topic.content_id == topic_content_id
	assert topic.node_id == topic_node_id

def test_topic_to_dict(topic, topic_json):
    assert topic.id == topic_json['id']
    assert topic.title == topic_json['title']
    assert topic.description == None
    assert topic.node_id.hex == topic_json['node_id']
    assert topic.content_id.hex == topic_json['content_id']
    assert topic.author == None
    assert topic.files == topic_json['files']
    assert topic.kind == topic_json['kind']
    assert topic.license == topic_json['license']



""" *********** VIDEO TESTS *********** """
def test_video_created(video):
	assert video is not None

def test_video_data(video, video_data):
	assert video.id == video_data['id']
	assert video.title == video_data['title']
	assert video.description == video_data['description']
	assert video.author == video_data['author']
	assert video.license == video_data['license']
	assert video.kind == constants.CK_VIDEO

def test_video_default_preset(video):
	assert video.default_preset == constants.FP_VIDEO_HIGH_RES

def test_video_derive_thumbnail(video):
	assert True

def test_video_transcode_to_lower_resolution(video):
	assert True

def test_video_ids(video, video_content_id, video_node_id):
	assert video.content_id == video_content_id
	assert video.node_id == video_node_id

def test_video_to_dict(video, video_json):
	assert video.to_dict() == video_json



""" *********** AUDIO TESTS *********** """
def test_audio_created(audio):
	assert audio is not None

def test_audio_data(audio, audio_data):
	assert audio.id == audio_data['id']
	assert audio.title == audio_data['title']
	assert audio.description == audio_data['description']
	assert audio.author == audio_data['author']
	assert audio.license == audio_data['license']
	assert audio.kind == constants.CK_AUDIO

def test_audio_default_preset(audio):
	assert audio.default_preset == constants.FP_AUDIO

def test_audio_ids(audio, audio_content_id, audio_node_id):
	assert audio.content_id == audio_content_id
	assert audio.node_id == audio_node_id

def test_audio_to_dict(audio, audio_json):
	assert audio.to_dict() == audio_json



""" *********** DOCUMENT TESTS *********** """
def test_document_created(document):
	assert document is not None

def test_document_data(document, document_data):
	assert document.id == document_data['id']
	assert document.title == document_data['title']
	assert document.description == document_data['description']
	assert document.author == document_data['author']
	assert document.license == document_data['license']
	assert document.kind == constants.CK_DOCUMENT

def test_document_default_preset(document):
	assert document.default_preset == constants.FP_DOCUMENT

def test_document_ids(document, document_content_id, document_node_id):
	assert document.content_id == document_content_id
	assert document.node_id == document_node_id

def test_document_to_dict(document, document_json):
	assert document.to_dict() == document_json



""" *********** EXERCISE TESTS *********** """
def test_exercise_created(exercise):
	assert exercise is not None

def test_exercise_data(exercise, exercise_data):
	assert exercise.id == exercise_data['id']
	assert exercise.title == exercise_data['title']
	assert exercise.description == exercise_data['description']
	assert exercise.author == exercise_data['author']
	assert exercise.license == exercise_data['license']
	assert exercise.kind == constants.CK_EXERCISE

def test_exercise_default_preset(exercise):
	assert exercise.default_preset == constants.FP_EXERCISE

def test_exercise_ids(exercise, exercise_content_id, exercise_node_id):
	assert exercise.content_id == exercise_content_id
	assert exercise.node_id == exercise_node_id

def test_exercise_to_dict(exercise, exercise_json):
	assert exercise.to_dict() == exercise_json
