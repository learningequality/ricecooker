""" Tests for handling requests to Kolibri Studio """

import copy
import pytest
import uuid
import tempfile
from le_utils.constants import licenses
import base64
from ricecooker.classes.nodes import *
from ricecooker.classes.files import *
from ricecooker.managers.tree import ChannelManager
from ricecooker.exceptions import InvalidNodeException


""" *********** CHANNEL FIXTURES *********** """
@pytest.fixture
def domain_namespace():
    return "learningequality.org"

@pytest.fixture
def source_id():
    return "sample-channel"

@pytest.fixture
def channel_domain_namespace(domain_namespace):
    return uuid.uuid5(uuid.NAMESPACE_DNS, domain_namespace)

@pytest.fixture
def channel_node_id(channel_domain_namespace, source_id):
    return uuid.uuid5(channel_domain_namespace, source_id)

@pytest.fixture
def channel_content_id(channel_domain_namespace, channel_node_id):
    return uuid.uuid5(channel_domain_namespace, channel_node_id.hex)

@pytest.fixture
def channel(domain_namespace, source_id):
    channel = ChannelNode(
        source_id,
        domain_namespace,
        "Channel",
        language="en"
    )
    return channel

@pytest.fixture
def invalid_channel(domain_namespace, source_id):
    channel = ChannelNode(
        source_id,
        domain_namespace,
        "Channel",
        language="en"
    )
    channel.source_id = None
    return channel

""" *********** TOPIC FIXTURES *********** """
@pytest.fixture
def topic_id():
    return "topic-id"

@pytest.fixture
def topic_content_id(channel_domain_namespace, topic_id):
    return uuid.uuid5(channel_domain_namespace, topic_id)

@pytest.fixture
def topic_node_id(channel_node_id, topic_content_id):
    return uuid.uuid5(channel_node_id, topic_content_id.hex)

@pytest.fixture
def topic(topic_id):
    return TopicNode(topic_id, "Topic")

@pytest.fixture
def invalid_topic(topic_id):
    topic = TopicNode(topic_id, "Topic")
    topic.title = None
    return topic

""" *********** DOCUMENT FIXTURES *********** """
@pytest.fixture
def document_id():
    return "document-id"

@pytest.fixture
def document_content_id(channel_domain_namespace, document_id):
    return uuid.uuid5(channel_domain_namespace, document_id)

@pytest.fixture
def document_node_id(topic_node_id, document_content_id):
    return uuid.uuid5(topic_node_id, document_content_id.hex)

@pytest.fixture
def document_file():
    return DocumentFile("document_path")

@pytest.fixture
def thumbnail_path():
    return "thumbnail path"

@pytest.fixture
def copyright_holder():
    return "Copyright Holder"

@pytest.fixture
def license_name():
    return licenses.PUBLIC_DOMAIN

@pytest.fixture
def document(document_id, document_file, thumbnail_path, copyright_holder, license_name):
    node = DocumentNode(document_id, "Document", licenses.CC_BY, thumbnail=thumbnail_path)
    node.add_file(document_file)
    node.set_license(license_name, copyright_holder=copyright_holder)
    return node

@pytest.fixture
def invalid_document(document_file):
    node = DocumentNode("invalid", "Document", licenses.CC_BY, files=[document_file])
    node.license = None
    return node


""" *********** TREE FIXTURES *********** """
@pytest.fixture
def tree(channel, topic, document):
    topic.add_child(document)
    channel.add_child(topic)
    return ChannelManager(channel)

@pytest.fixture
def invalid_tree(invalid_channel, invalid_topic, invalid_document):
    invalid_topic.add_child(invalid_document)
    invalid_channel.add_child(invalid_topic)
    return ChannelManager(invalid_channel)

@pytest.fixture
def invalid_tree_2(channel, topic, invalid_document):
    channel_copy = copy.deepcopy(channel)
    topic_copy = copy.deepcopy(topic)
    topic_copy.add_child(invalid_document)
    channel_copy.add_child(topic_copy)
    return ChannelManager(channel_copy)


""" TESTS """
def test_validate(tree, invalid_tree, invalid_tree_2):
    assert tree.validate(), "Tree should pass validation"
    pytest.raises(InvalidNodeException, invalid_tree.validate)
    pytest.raises(InvalidNodeException, invalid_tree_2.validate)

def test_check_for_files_failed():
    assert True

def test_get_file_diff():
    assert True

def test_upload_files():
    assert True

def test_reattempt_upload_fails():
    assert True

def test_upload_tree():
    assert True

def test_reattempt_failed():
    assert True

def test_add_channel():
    assert True

def test_add_nodes():
    assert True

def test_commit_channel():
    assert True

def test_publish():
    assert True