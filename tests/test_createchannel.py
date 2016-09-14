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
        "id" : channel_uuid,
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
        "description": topic_data['description'],
        "node_id": topic_node_id.hex,
        "content_id": topic_content_id.hex,
        "author": topic_data['author'],
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
        "description": video_data['description'],
        "node_id": video_node_id.hex,
        "content_id": video_content_id.hex,
        "author": video_data['author'],
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
        "description": audio_data['description'],
        "node_id": audio_node_id.hex,
        "content_id": audio_content_id.hex,
        "author": audio_data['author'],
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
        "description": document_data['description'],
        "node_id": document_node_id.hex,
        "content_id": document_content_id.hex,
        "author": document_data['author'],
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
        "description": exercise_data['description'],
        "node_id": exercise_node_id.hex,
        "content_id": exercise_content_id.hex,
        "author": exercise_data['author'],
        "children": [],
        "files": [],
        "kind": constants.CK_EXERCISE,
        "license": exercise_data['license'],
    }
