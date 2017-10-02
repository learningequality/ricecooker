""" Tests for tree construction """

import copy
import pytest
import uuid
from le_utils.constants import licenses
from ricecooker.classes.nodes import *
from ricecooker.classes.files import *
from ricecooker.classes.licenses import *
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
        source_id=source_id,
        source_domain=domain_namespace,
        title='Channel',
        language='en'
    )
    return channel

@pytest.fixture
def invalid_channel(domain_namespace, source_id):
    channel = ChannelNode(
        source_id=source_id,
        source_domain=domain_namespace,
        title='Channel',
        language='en'
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
    return channel

@pytest.fixture
def invalid_tree(invalid_channel, invalid_topic, invalid_document):
    invalid_topic.add_child(invalid_document)
    invalid_channel.add_child(invalid_topic)
    return invalid_channel

@pytest.fixture
def invalid_tree_2(channel, topic, invalid_document):
    channel_copy = copy.deepcopy(channel)
    topic_copy = copy.deepcopy(topic)
    topic_copy.add_child(invalid_document)
    channel_copy.add_child(topic_copy)
    return channel_copy

""" *********** CONTENT NODE TESTS *********** """
def test_nodes_initialized(channel, topic, document):
    assert channel
    assert topic
    assert document

def test_add_child(tree, topic, document):
    assert tree.children[0] == topic, "Channel should have topic child node"
    assert tree.children[0].children[0] == document, "Topic should have a document child node"

def test_ids(tree, channel_node_id, channel_content_id, topic_content_id, topic_node_id, document_content_id, document_node_id):
    channel = tree
    topic = tree.children[0]
    document = topic.children[0]

    assert channel.get_content_id() == channel_content_id, "Channel content id should be {}".format(channel_content_id)
    assert channel.get_node_id() == channel_node_id, "Channel node id should be {}".format(channel_node_id)
    assert topic.get_content_id() == topic_content_id, "Topic content id should be {}".format(topic_content_id)
    assert topic.get_node_id() == topic_node_id, "Topic node id should be {}".format(topic_node_id)
    assert document.get_content_id() == document_content_id, "Document content id should be {}".format(document_content_id)
    assert document.get_node_id() == document_node_id, "Document node id should be {}".format(document_node_id)

def test_add_file(document, document_file):
    test_files = list(filter(lambda f: isinstance(f, DocumentFile), document.files))
    assert any(test_files), "Document must have at least one file"
    assert test_files[0] == document_file, "Document file was not added correctly"

def test_thumbnail(topic, document, thumbnail_path):
    assert document.has_thumbnail(), "Document must have a thumbnail"
    assert not topic.has_thumbnail(), "Topic must not have a thumbnail"
    assert any(filter(lambda f: f.path == thumbnail_path, document.files)), "Document is missing a thumbnail with path {}".format(thumbnail_path)

def test_count(tree):
    assert tree.count() == 2, "Channel should have 2 descendants"

def test_get_non_topic_descendants(tree, document):
    assert tree.get_non_topic_descendants() == [document], "Channel should only have 1 non-topic descendant"

def test_licenses(channel, topic, document, license_name, copyright_holder):
    assert isinstance(document.license, License), "Document should have a license object"
    assert document.license.license_id == license_name, "Document license should have public domain license"
    assert document.license.copyright_holder == copyright_holder, "Document license should have copyright holder set to {}".format(copyright_holder)
    assert not channel.license, "Channel should not have a license"
    assert not topic.license, "Topic should not have a license"

def test_tree_validation(tree, invalid_tree, invalid_tree_2):
    assert tree.test_tree(), "Valid tree should pass validation"

    try:
        invalid_tree.test_tree()
        assert False, "Invalid tree should fail validation"
    except InvalidNodeException:
        pass

    try:
        invalid_tree_2.test_tree()
        assert False, "Invalid tree should fail validation"
    except InvalidNodeException:
        pass

