""" Tests for tree construction """

import copy
import pytest
import uuid
from le_utils.constants import licenses
from ricecooker.classes.nodes import *
from ricecooker.classes.files import *
from ricecooker.classes.licenses import *
from ricecooker.exceptions import InvalidNodeException
from ricecooker.utils.zip import create_predictable_zip


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
def thumbnail_path():
    return "tests/testcontent/samples/thumbnail.png"

@pytest.fixture
def thumbnail_path_jpg():
    return "tests/testcontent/samples/thumbnail.jpg"

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
    test_files = [f for f in document.files if isinstance(f, DocumentFile)]
    assert any(test_files), "Document must have at least one file"
    assert test_files[0] == document_file, "Document file was not added correctly"

def test_thumbnail(topic, document, thumbnail_path):
    assert document.has_thumbnail(), "Document must have a thumbnail"
    assert not topic.has_thumbnail(), "Topic must not have a thumbnail"
    assert [f for f in document.files if f.path == thumbnail_path], "Document is missing a thumbnail with path {}".format(thumbnail_path)

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

def test_validate_tree(tree, invalid_tree, invalid_tree_2):
    assert tree.validate_tree(), "Valid tree should pass validation"

    try:
        invalid_tree.validate_tree()
        assert False, "Invalid tree should fail validation"
    except InvalidNodeException:
        pass

    try:
        invalid_tree_2.validate_tree()
        assert False, "Invalid tree should fail validation"
    except InvalidNodeException:
        pass










""" *********** SLIDESHOW CONTENT NODE TESTS *********** """


def test_slideshow_node_via_files(channel):
    slideshow_node = SlideshowNode(
        title="The Slideshow",
        description="Slideshow Content Demo",
        source_id='demo',
        author="DE Mo",
        language='en',
        license=get_license('CC BY', copyright_holder='Demo Holdings'),
        files=[
            SlideImageFile(
                path='tests/testcontent/samples/thumbnail.jpg',
                language='en',
                caption="Demo blocks are neat.",
                descriptive_text="Demo blocks are neat."
            ),
            SlideImageFile(
                path='tests/testcontent/samples/thumbnail.jpg',
                language='en',
                caption="Touch the demo to learn new things!",
                descriptive_text="Touch the demo to learn new things!"
            ),
            SlideImageFile(
                path='tests/testcontent/samples/thumbnail.jpg',
                language='en',
                caption="Made mostly with Python!",
                descriptive_text="Made mostly with Python!"
            ),
            SlideImageFile(
                path='tests/testcontent/samples/thumbnail.jpg',
                language='en',
                caption="Unlock your potential with this demo.",
                descriptive_text="Unlock your potential with this demo."
            ),
            ThumbnailFile(
                path='tests/testcontent/samples/thumbnail.png',
                language='en'
            )
        ]
    )
    assert slideshow_node
    assert slideshow_node.kind == 'slideshow'
    assert len(slideshow_node.files) == 5, 'missing files'
    assert slideshow_node.extra_fields, 'missing extra_fields'
    assert 'slideshow_data' in slideshow_node.extra_fields, 'missing slideshow_data key'
    slideshow_node.process_files()
    channel.add_child(slideshow_node)
    assert channel.validate_tree()
    assert slideshow_node.to_dict() # not ready yet bcs needs ot be part of tree...



def test_slideshow_node_via_add_file(channel):
    slideshow_node = SlideshowNode(
        title="The Slideshow via add_files",
        description="Slideshow Content Demo",
        source_id='demo2',
        author="DE Mo",
        language='en',
        license=get_license('CC BY', copyright_holder='Demo Holdings'),
        files=[]
    )
    slideimg1 = SlideImageFile(
        path='tests/testcontent/samples/thumbnail.jpg',
        language='en',
        caption="Demo blocks are neat.",
        descriptive_text="Demo blocks are neat."
    )
    slideshow_node.add_file(slideimg1)
    slideimg2 = SlideImageFile(
        path='tests/testcontent/samples/thumbnail.jpg',
        language='en',
        caption="Touch the demo to learn new things!",
        descriptive_text="Touch the demo to learn new things!"
    )
    slideshow_node.add_file(slideimg2)
    thumbimg1 = ThumbnailFile(
        path='tests/testcontent/samples/thumbnail.jpg',
        language='en'
    )
    slideshow_node.add_file(thumbimg1)

    # print(slideshow_node.__dict__)
    assert slideshow_node
    assert len(slideshow_node.files) == 3, 'missing files'

    channel.add_child(slideshow_node)
    assert channel.validate_tree()


""" *********** CUSTOM NAVIGATION CONTENT NODE TESTS *********** """


def test_custom_navigation_node_via_files(channel):
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir,'index.html'), 'w') as testf:
        testf.write('something something')
    zip_path = create_predictable_zip(inputdir)

    custom_navigation_node = CustomNavigationNode(
        title="The Nav App",
        description="Custom Navigation Content Demo",
        source_id='demo',
        author="DE Mo",
        language='en',
        license=get_license('CC BY', copyright_holder='Demo Holdings'),
        files=[
            HTMLZipFile(
                path=zip_path,
                language='en',
            ),
            ThumbnailFile(
                path='tests/testcontent/samples/thumbnail.png',
                language='en'
            )
        ]
    )
    assert custom_navigation_node
    assert custom_navigation_node.kind == 'topic'
    assert len(custom_navigation_node.files) == 2, 'missing files'
    assert custom_navigation_node.extra_fields, 'missing extra_fields'
    assert 'modality' in custom_navigation_node.extra_fields and custom_navigation_node.extra_fields["modality"] == "CUSTOM_NAVIGATION", 'missing custom navigation modality'
    custom_navigation_node.process_files()
    channel.add_child(custom_navigation_node)
    assert channel.validate_tree()
    assert custom_navigation_node.to_dict()



def test_custom_navigation_node_via_add_file(channel):
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir,'index.html'), 'w') as testf:
        testf.write('something something')
    zip_path = create_predictable_zip(inputdir)
    custom_navigation_node = CustomNavigationNode(
        title="The Slideshow via add_files",
        description="Slideshow Content Demo",
        source_id='demo2',
        author="DE Mo",
        language='en',
        license=get_license('CC BY', copyright_holder='Demo Holdings'),
        files=[]
    )
    zipfile = HTMLZipFile(
        path=zip_path,
        language='en',
    )
    custom_navigation_node.add_file(zipfile)
    thumbimg1 = ThumbnailFile(
        path='tests/testcontent/samples/thumbnail.jpg',
        language='en'
    )
    custom_navigation_node.add_file(thumbimg1)

    assert custom_navigation_node
    assert custom_navigation_node.kind == 'topic'
    assert len(custom_navigation_node.files) == 2, 'missing files'
    assert custom_navigation_node.extra_fields, 'missing extra_fields'
    assert 'modality' in custom_navigation_node.extra_fields and custom_navigation_node.extra_fields["modality"] == "CUSTOM_NAVIGATION", 'missing custom navigation modality'
    custom_navigation_node.process_files()
    channel.add_child(custom_navigation_node)
    assert channel.validate_tree()
    assert custom_navigation_node.to_dict()


""" *********** CUSTOM NAVIGATION CHANNEL NODE TESTS *********** """


def test_custom_navigation_channel_node_via_files():
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir,'index.html'), 'w') as testf:
        testf.write('something something')
    zip_path = create_predictable_zip(inputdir)
    zipfile = HTMLZipFile(
        path=zip_path,
        language='en',
    )
    thumbimg1 = ThumbnailFile(
        path='tests/testcontent/samples/thumbnail.png',
        language='en'
    )
    custom_navigation_channel_node = CustomNavigationChannelNode(
        title="The Nav App",
        description="Custom Navigation Content Demo",
        source_id='demo',
        source_domain='DEMO',
        language='en',
        files=[
            zipfile,
            thumbimg1,
        ]
    )
    assert custom_navigation_channel_node
    assert custom_navigation_channel_node.kind == 'Channel'
    assert len(custom_navigation_channel_node.files) == 2, 'missing files'
    assert custom_navigation_channel_node.extra_fields, 'missing extra_fields'
    assert 'modality' in custom_navigation_channel_node.extra_fields and custom_navigation_channel_node.extra_fields["modality"] == "CUSTOM_NAVIGATION", 'missing custom navigation modality'
    custom_navigation_channel_node.set_thumbnail(thumbimg1)
    custom_navigation_channel_node.process_files()
    assert custom_navigation_channel_node.validate_tree()
    assert custom_navigation_channel_node.to_dict()
    assert custom_navigation_channel_node.to_dict()["thumbnail"] == thumbimg1.filename
    assert len(custom_navigation_channel_node.to_dict()["files"]) == 1
    assert custom_navigation_channel_node.to_dict()["files"][0]["filename"] == zipfile.filename


def test_custom_navigation_channel_node_via_add_file():
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir,'index.html'), 'w') as testf:
        testf.write('something something')
    zip_path = create_predictable_zip(inputdir)
    custom_navigation_channel_node = CustomNavigationChannelNode(
        title="The Slideshow via add_files",
        description="Slideshow Content Demo",
        source_id='demo2',
        source_domain='DEMO',
        language='en',
        files=[]
    )
    zipfile = HTMLZipFile(
        path=zip_path,
        language='en',
    )
    custom_navigation_channel_node.add_file(zipfile)
    thumbimg1 = ThumbnailFile(
        path='tests/testcontent/samples/thumbnail.jpg',
        language='en'
    )
    custom_navigation_channel_node.add_file(thumbimg1)

    assert custom_navigation_channel_node
    assert custom_navigation_channel_node.kind == 'Channel'
    assert len(custom_navigation_channel_node.files) == 2, 'missing files'
    assert custom_navigation_channel_node.extra_fields, 'missing extra_fields'
    assert 'modality' in custom_navigation_channel_node.extra_fields and custom_navigation_channel_node.extra_fields["modality"] == "CUSTOM_NAVIGATION", 'missing custom navigation modality'
    custom_navigation_channel_node.set_thumbnail(thumbimg1)
    custom_navigation_channel_node.process_files()
    assert custom_navigation_channel_node.validate_tree()
    assert custom_navigation_channel_node.to_dict()
    assert custom_navigation_channel_node.to_dict()["thumbnail"] == thumbimg1.filename
    assert len(custom_navigation_channel_node.to_dict()["files"]) == 1
    assert custom_navigation_channel_node.to_dict()["files"][0]["filename"] == zipfile.filename
