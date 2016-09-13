import pytest
import uuid
from ricecooker.classes import Channel

@pytest.fixture
def channel_id():
    return "sample-channel"

@pytest.fixture
def channel_uuid(channel_id):
    return uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, channel_id).hex).hex

@pytest.fixture
def channel_data(channel_id):
    return {
    	"domain" : "learningequality.org",
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

def test_channel_created(channel):
	assert channel is not None

def test_channel_data(channel, channel_data, channel_uuid):
	assert channel.domain == channel_data['domain']
	assert channel.title == channel_data['title']
	assert channel.channel_id == channel_uuid