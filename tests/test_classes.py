import pytest
import uuid
from fle_utils import constants
from ricecooker.classes import *


""" *********** CHANNEL FIXTURES *********** """
@pytest.fixture
def channel_id():
    return "sample-channel"

@pytest.fixture
def channel_domain():
    return "learningequality.org"

@pytest.fixture
def channel_uuid(channel_id):
    return uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, channel_id).hex).hex

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



""" *********** TOPIC FIXTURES *********** """
@pytest.fixture
def topic_id():
    return "topic-id"

@pytest.fixture
def topic_data(topic_id):
    return {
    	"title": "topic node test",
    	"description": None,
        "id" : topic_id,
        "author": None,
    }

@pytest.fixture
def topic(topic_data):
    return Topic(
		id=topic_data['id'],
		description=topic_data['description'],
		title=topic_data['title'],
		author=topic_data['author']
	)



""" *********** VIDEO FIXTURES *********** """
@pytest.fixture
def video_id():
    return "video-id"

@pytest.fixture
def video_data(video_id):
    return {
    	"title": "video node test",
    	"description": None,
        "id" : video_id,
        "author": None,
    }

@pytest.fixture
def video(video_data):
    return Video(
		id=video_data['id'],
		description=video_data['description'],
		title=video_data['title'],
		author=video_data['author'],
		transcode_to_lower_resolutions=True,
		derive_thumbnail=True,
	)



""" *********** AUDIO FIXTURES *********** """
@pytest.fixture
def audio_id():
    return "audio-id"

@pytest.fixture
def audio_data(audio_id):
    return {
    	"title": "audio node test",
    	"description": None,
        "id" : audio_id,
        "author": None,
    }

@pytest.fixture
def audio(audio_data):
    return Audio(
		id=audio_data['id'],
		description=audio_data['description'],
		title=audio_data['title'],
		author=audio_data['author'],
	)



""" *********** DOCUMENT FIXTURES *********** """
@pytest.fixture
def document_id():
    return "document-id"

@pytest.fixture
def document_data(document_id):
    return {
    	"title": "document node test",
    	"description": None,
        "id" : document_id,
        "author": None,
    }

@pytest.fixture
def document(document_data):
    return Document(
		id=document_data['id'],
		description=document_data['description'],
		title=document_data['title'],
		author=document_data['author'],
	)



""" *********** EXERCISE FIXTURES *********** """
@pytest.fixture
def exercise_id():
    return "exercise-id"

@pytest.fixture
def exercise_data(exercise_id):
    return {
    	"title": "exercise node test",
    	"description": None,
        "id" : exercise_id,
        "author": None,
    }

@pytest.fixture
def exercise(exercise_data):
    return Exercise(
		id=exercise_data['id'],
		description=exercise_data['description'],
		title=exercise_data['title'],
		author=exercise_data['author'],
	)



""" *********** CHANNEL TESTS *********** """
def test_channel_created(channel):
	assert channel is not None

def test_channel_data(channel, channel_data, channel_uuid):
	assert channel.domain == channel_data['domain']
	assert channel.title == channel_data['title']
	assert channel.channel_id == channel_uuid

def test_channel_root(channel):
	assert channel.root is not None
	assert channel.root.kind == constants.CK_TOPIC



""" *********** TOPIC TESTS *********** """
def test_topic_created(topic):
	assert topic is not None

def test_topic_data(topic, topic_data):
	assert topic.id == topic_data['id']
	assert topic.title == topic_data['title']
	assert topic.description == topic_data['description']
	assert topic.author == topic_data['author']
	assert topic.kind == constants.CK_TOPIC

def test_topic_ids(topic):
	assert True



""" *********** VIDEO TESTS *********** """
def test_video_created(video):
	assert video is not None

def test_video_data(video, video_data):
	assert video.id == video_data['id']
	assert video.title == video_data['title']
	assert video.description == video_data['description']
	assert video.author == video_data['author']
	assert video.kind == constants.CK_VIDEO

def test_video_default_preset(video):
	assert video.default_preset == constants.FP_VIDEO_HIGH_RES

def test_video_derive_thumbnail(video):
	assert True

def test_video_transcode_to_lower_resolution(video):
	assert True



""" *********** AUDIO TESTS *********** """
def test_audio_created(audio):
	assert audio is not None

def test_audio_data(audio, audio_data):
	assert audio.id == audio_data['id']
	assert audio.title == audio_data['title']
	assert audio.description == audio_data['description']
	assert audio.author == audio_data['author']
	assert audio.kind == constants.CK_AUDIO

def test_audio_default_preset(audio):
	assert audio.default_preset == constants.FP_AUDIO



""" *********** DOCUMENT TESTS *********** """
def test_document_created(document):
	assert document is not None

def test_document_data(document, document_data):
	assert document.id == document_data['id']
	assert document.title == document_data['title']
	assert document.description == document_data['description']
	assert document.author == document_data['author']
	assert document.kind == constants.CK_DOCUMENT

def test_document_default_preset(document):
	assert document.default_preset == constants.FP_DOCUMENT



""" *********** EXERCISE TESTS *********** """
def test_exercise_created(exercise):
	assert exercise is not None

def test_exercise_data(exercise, exercise_data):
	assert exercise.id == exercise_data['id']
	assert exercise.title == exercise_data['title']
	assert exercise.description == exercise_data['description']
	assert exercise.author == exercise_data['author']
	assert exercise.kind == constants.CK_EXERCISE

def test_exercise_default_preset(exercise):
	assert exercise.default_preset == constants.FP_EXERCISE
