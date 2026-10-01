"""Tests for tree construction"""

import json
import logging
import os
import tempfile
import uuid
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
import requests
from conftest import sample_path
from fake_session import fake_download_session
from le_utils.constants import content_kinds
from le_utils.constants import exercises
from le_utils.constants import file_types
from le_utils.constants import format_presets
from le_utils.constants import licenses
from le_utils.constants.labels import accessibility_categories
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import levels
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type
from le_utils.constants.labels import subjects
from le_utils.constants.languages import getlang
from PIL import Image
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout
from test_videos import _clear_ricecookerfilecache

from ricecooker import config
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.files import ThumbnailFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.licenses import License
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import CustomNavigationChannelNode
from ricecooker.classes.nodes import CustomNavigationNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import ExerciseNode
from ricecooker.classes.nodes import METADATA_LABEL_CHOICES
from ricecooker.classes.nodes import Node
from ricecooker.classes.nodes import RemoteContentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import TreeNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.classes.questions import PerseusQuestion
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.commands import uploadchannel
from ricecooker.exceptions import ChannelIncompleteError
from ricecooker.exceptions import FileNotFoundException
from ricecooker.exceptions import InvalidNodeException
from ricecooker.managers.tree import ChannelManager
from ricecooker.managers.tree import InsufficientStorageException
from ricecooker.utils.jsontrees import build_tree_from_json
from ricecooker.utils.pipeline import FilePipeline
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
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "samples", "thumbnail.png"
        )
    )
    # return "testcontent/samples/thumbnail.png"


@pytest.fixture
def thumbnail_path_jpg():
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "samples", "thumbnail.jpg"
        )
    )
    # return "tests/testcontent/samples/thumbnail.jpg"


@pytest.fixture
def copyright_holder():
    return "Copyright Holder"


@pytest.fixture
def license_name():
    return licenses.PUBLIC_DOMAIN


@pytest.fixture
def document(
    document_id, document_file, thumbnail_path, copyright_holder, license_name
):
    node = DocumentNode(
        document_id, "Document", licenses.CC_BY, thumbnail=thumbnail_path
    )
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


""" *********** CONTENT NODE TESTS *********** """


def test_nodes_initialized(channel, topic, document):
    assert channel
    assert topic
    assert document


def test_add_child(tree, topic, document):
    assert tree.children[0] == topic, "Channel should have topic child node"
    assert tree.children[0].children[0] == document, (
        "Topic should have a document child node"
    )


def test_ids(
    tree,
    channel_node_id,
    channel_content_id,
    topic_content_id,
    topic_node_id,
    document_content_id,
    document_node_id,
):
    channel = tree
    topic = tree.children[0]
    document = topic.children[0]

    assert channel.get_content_id() == channel_content_id, (
        "Channel content id should be {}".format(channel_content_id)
    )
    assert channel.get_node_id() == channel_node_id, (
        "Channel node id should be {}".format(channel_node_id)
    )
    assert topic.get_content_id() == topic_content_id, (
        "Topic content id should be {}".format(topic_content_id)
    )
    assert topic.get_node_id() == topic_node_id, "Topic node id should be {}".format(
        topic_node_id
    )
    assert document.get_content_id() == document_content_id, (
        "Document content id should be {}".format(document_content_id)
    )
    assert document.get_node_id() == document_node_id, (
        "Document node id should be {}".format(document_node_id)
    )


def test_add_file(document, document_file):
    test_files = [f for f in document.files if isinstance(f, DocumentFile)]
    assert any(test_files), "Document must have at least one file"
    assert test_files[0] == document_file, "Document file was not added correctly"


def test_thumbnail(topic, document, thumbnail_path):
    assert document.has_thumbnail(), "Document must have a thumbnail"
    assert not topic.has_thumbnail(), "Topic must not have a thumbnail"
    assert [f for f in document.files if f.path == thumbnail_path], (
        "Document is missing a thumbnail with path {}".format(thumbnail_path)
    )


def test_count(tree):
    assert tree.count() == 2, "Channel should have 2 descendants"


def test_get_non_topic_descendants(tree, document):
    assert tree.get_non_topic_descendants() == [document], (
        "Channel should only have 1 non-topic descendant"
    )


def test_licenses(channel, topic, document, license_name, copyright_holder):
    assert isinstance(document.license, License), (
        "Document should have a license object"
    )
    assert document.license.license_id == license_name, (
        "Document license should have public domain license"
    )
    assert document.license.copyright_holder == copyright_holder, (
        "Document license should have copyright holder set to {}".format(
            copyright_holder
        )
    )
    assert not channel.license, "Channel should not have a license"
    assert not topic.license, "Topic should not have a license"


def test_validate_topics(tree, invalid_tree):
    assert tree.validate() is None, "Valid topic should pass validation"

    try:
        invalid_tree.validate()
        assert False, "Invalid topic should fail validation"
    except InvalidNodeException:
        pass


""" *********** ADD files  TESTS"""


def test_add_files_with_preset(channel):
    topic_node = dict(
        kind=content_kinds.TOPIC,
        source_id="test:container",
        title="test title",
        language=getlang("ar").code,
        children=[],
    )
    audio_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "media_utils",
            "audio",
            "file_example_MP3_700KB.mp3",
        )
    )
    # audio_path = os.path.join("tests/media_utils/audio/file_example_MP3_700KB.mp3")

    audio_node = dict(
        kind=content_kinds.AUDIO,
        source_id="audio_node",
        title="audio_node",
        description="audio_node description",
        language=getlang("ar").code,
        license=get_license("CC BY", copyright_holder="Demo Holdings").as_dict(),
        author="author name",
        files=[
            {
                "file_type": file_types.AUDIO,
                "path": audio_path,
                "language": getlang("ar").code,
            }
        ],
    )

    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir, "index.html"), "w") as testf:
        testf.write("something something")
    zip_path = create_predictable_zip(inputdir)

    files = [
        {
            "file_type": file_types.HTML5,
            "path": zip_path,
            "language": getlang("ar").code,
        },
        {
            "file_type": file_types.AUDIO,
            "path": audio_path,
            "language": getlang("ar").code,
            "preset": format_presets.AUDIO_DEPENDENCY,
        },
    ]

    html5_dict = dict(
        kind=content_kinds.HTML5,
        source_id="source_test_id",
        title="source_test_id",
        description="test_description",
        language=getlang("ar").code,
        license=get_license("CC BY", copyright_holder="Demo Holdings").as_dict(),
        author="Test author",
        thumbnail="tests/testcontent/samples/thumbnail.jpg",
        files=files,
    )
    topic_node["children"].append(html5_dict)
    topic_node["children"].append(audio_node)
    parent_node = build_tree_from_json(channel, [topic_node])
    topic_node = parent_node.children[0]
    html5_node = topic_node.children[0]
    parent_node.validate()
    assert parent_node
    assert parent_node.children[0]
    assert topic_node.kind == "topic"
    assert len(html5_node.files) == 3
    assert html5_node.files[2].get_preset() == format_presets.AUDIO_DEPENDENCY


def test_jsontrees_perseus_question_without_ka_language_fails_node(
    channel, mastery_model
):
    exercise = dict(
        kind=content_kinds.EXERCISE,
        source_id="exercise",
        title="exercise",
        license=get_license("CC BY", copyright_holder="Demo Holdings").as_dict(),
        exercise_data=mastery_model,
        questions=[
            {"question_type": exercises.PERSEUS_QUESTION, "id": "q1", "item_data": "{}"}
        ],
    )
    build_tree_from_json(channel, [exercise])
    with pytest.raises(InvalidNodeException, match="question q1: .*ka_language"):
        channel.children[0].validate()


def test_jsontrees_slideshow_node_unsupported(channel):
    slideshow = dict(
        kind=content_kinds.SLIDESHOW,
        source_id="slideshow",
        title="slideshow",
        license=get_license("CC BY", copyright_holder="Demo Holdings").as_dict(),
    )
    with pytest.raises(
        NotImplementedError, match="Unexpected node kind found in json data."
    ):
        build_tree_from_json(channel, [slideshow])


def test_jsontrees_slideshow_image_file_unsupported(channel):
    document = dict(
        kind=content_kinds.DOCUMENT,
        source_id="document",
        title="document",
        license=get_license("CC BY", copyright_holder="Demo Holdings").as_dict(),
        files=[
            {
                "file_type": file_types.SLIDESHOW_IMAGE,
                "path": "tests/testcontent/samples/thumbnail.jpg",
            }
        ],
    )
    with pytest.raises(NotImplementedError, match="Unexpected File type"):
        build_tree_from_json(channel, [document])


""" *********** CUSTOM NAVIGATION CONTENT NODE TESTS *********** """


def test_custom_navigation_node_via_files(channel):
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir, "index.html"), "w") as testf:
        testf.write("something something")
    zip_path = create_predictable_zip(inputdir)

    custom_navigation_node = CustomNavigationNode(
        title="The Nav App",
        description="Custom Navigation Content Demo",
        source_id="demo",
        author="DE Mo",
        language="en",
        license=get_license("CC BY", copyright_holder="Demo Holdings"),
        files=[
            HTMLZipFile(path=zip_path, language="en"),
            ThumbnailFile(
                path="tests/testcontent/samples/thumbnail.png", language="en"
            ),
        ],
    )
    assert custom_navigation_node
    assert custom_navigation_node.kind == "topic"
    assert len(custom_navigation_node.files) == 2, "missing files"
    assert custom_navigation_node.extra_fields, "missing extra_fields"
    assert (
        "options" in custom_navigation_node.extra_fields
        and "modality" in custom_navigation_node.extra_fields["options"]
        and custom_navigation_node.extra_fields["options"]["modality"]
        == "CUSTOM_NAVIGATION"
    ), "missing custom navigation modality"
    custom_navigation_node.process_files()
    channel.add_child(custom_navigation_node)
    channel.validate()
    assert custom_navigation_node.to_dict()


def test_custom_navigation_node_via_add_file(channel):
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir, "index.html"), "w") as testf:
        testf.write("something something")
    zip_path = create_predictable_zip(inputdir)
    custom_navigation_node = CustomNavigationNode(
        title="The Slideshow via add_files",
        description="Slideshow Content Demo",
        source_id="demo2",
        author="DE Mo",
        language="en",
        license=get_license("CC BY", copyright_holder="Demo Holdings"),
        files=[],
    )
    zipfile = HTMLZipFile(path=zip_path, language="en")
    custom_navigation_node.add_file(zipfile)
    thumbimg1 = ThumbnailFile(
        path="tests/testcontent/samples/thumbnail.jpg", language="en"
    )
    custom_navigation_node.add_file(thumbimg1)

    assert custom_navigation_node
    assert custom_navigation_node.kind == "topic"
    assert len(custom_navigation_node.files) == 2, "missing files"
    assert custom_navigation_node.extra_fields, "missing extra_fields"
    assert (
        "options" in custom_navigation_node.extra_fields
        and "modality" in custom_navigation_node.extra_fields["options"]
        and custom_navigation_node.extra_fields["options"]["modality"]
        == "CUSTOM_NAVIGATION"
    ), "missing custom navigation modality"
    custom_navigation_node.process_files()
    channel.add_child(custom_navigation_node)
    channel.validate()
    assert custom_navigation_node.to_dict()


""" *********** CUSTOM NAVIGATION CHANNEL NODE TESTS *********** """


def test_custom_navigation_channel_node_via_files():
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir, "index.html"), "w") as testf:
        testf.write("something something")
    zip_path = create_predictable_zip(inputdir)
    zipfile = HTMLZipFile(path=zip_path, language="en")
    thumbimg1 = ThumbnailFile(
        path="tests/testcontent/samples/thumbnail.png", language="en"
    )
    custom_navigation_channel_node = CustomNavigationChannelNode(
        title="The Nav App",
        description="Custom Navigation Content Demo",
        source_id="demo",
        source_domain="DEMO",
        language="en",
        files=[zipfile, thumbimg1],
    )
    assert custom_navigation_channel_node
    assert custom_navigation_channel_node.kind == "Channel"
    assert len(custom_navigation_channel_node.files) == 2, "missing files"
    assert custom_navigation_channel_node.extra_fields, "missing extra_fields"
    assert (
        "options" in custom_navigation_channel_node.extra_fields
        and "modality" in custom_navigation_channel_node.extra_fields["options"]
        and custom_navigation_channel_node.extra_fields["options"]["modality"]
        == "CUSTOM_NAVIGATION"
    ), "missing custom navigation modality"
    custom_navigation_channel_node.set_thumbnail(thumbimg1)
    custom_navigation_channel_node.process_files()
    custom_navigation_channel_node.validate()
    assert custom_navigation_channel_node.to_dict()
    assert custom_navigation_channel_node.to_dict()["thumbnail"] == thumbimg1.filename
    assert len(custom_navigation_channel_node.to_dict()["files"]) == 1
    assert (
        custom_navigation_channel_node.to_dict()["files"][0]["filename"]
        == zipfile.filename
    )


def test_custom_navigation_channel_node_via_add_file():
    inputdir = tempfile.mkdtemp()
    with open(os.path.join(inputdir, "index.html"), "w") as testf:
        testf.write("something something")
    zip_path = create_predictable_zip(inputdir)
    custom_navigation_channel_node = CustomNavigationChannelNode(
        title="The Slideshow via add_files",
        description="Slideshow Content Demo",
        source_id="demo2",
        source_domain="DEMO",
        language="en",
        files=[],
    )
    zipfile = HTMLZipFile(path=zip_path, language="en")
    custom_navigation_channel_node.add_file(zipfile)
    thumbimg1 = ThumbnailFile(
        path="tests/testcontent/samples/thumbnail.jpg", language="en"
    )
    custom_navigation_channel_node.add_file(thumbimg1)

    assert custom_navigation_channel_node
    assert custom_navigation_channel_node.kind == "Channel"
    assert len(custom_navigation_channel_node.files) == 2, "missing files"
    assert custom_navigation_channel_node.extra_fields, "missing extra_fields"
    assert (
        "options" in custom_navigation_channel_node.extra_fields
        and "modality" in custom_navigation_channel_node.extra_fields["options"]
        and custom_navigation_channel_node.extra_fields["options"]["modality"]
        == "CUSTOM_NAVIGATION"
    ), "missing custom navigation modality"
    custom_navigation_channel_node.set_thumbnail(thumbimg1)
    custom_navigation_channel_node.process_files()
    custom_navigation_channel_node.validate()
    assert custom_navigation_channel_node.to_dict()
    assert custom_navigation_channel_node.to_dict()["thumbnail"] == thumbimg1.filename
    assert len(custom_navigation_channel_node.to_dict()["files"]) == 1
    assert (
        custom_navigation_channel_node.to_dict()["files"][0]["filename"]
        == zipfile.filename
    )


def test_remote_content_node_with_no_overrides():
    remote_content_node = RemoteContentNode(
        "a" * 32,
        source_node_id="b" * 32,
        source_content_id="c" * 32,
    )
    assert remote_content_node
    assert remote_content_node.kind == "remotecontent"
    assert len(remote_content_node.files) == 0
    remote_content_node.validate()
    output = remote_content_node.to_dict()
    assert output.get("title") is None
    assert output.get("description") is None


def test_remote_content_node_with_basic_overrides():
    remote_content_node = RemoteContentNode(
        "a" * 32,
        source_content_id="c" * 32,
        title="My Title",
        description="My Description",
    )
    assert remote_content_node
    assert remote_content_node.kind == "remotecontent"
    assert len(remote_content_node.files) == 0
    remote_content_node.validate()
    output = remote_content_node.to_dict()
    assert output.get("title") == "My Title"
    assert output.get("description") == "My Description"


def test_remote_content_node_with_provider_override():
    remote_content_node = RemoteContentNode(
        "a" * 32,
        source_node_id="b" * 32,
        provider="Doctor Tibbles",
    )
    assert remote_content_node
    assert remote_content_node.kind == "remotecontent"
    assert len(remote_content_node.files) == 0
    remote_content_node.validate()
    output = remote_content_node.to_dict()
    assert output.get("provider") == "Doctor Tibbles"


def test_remote_content_node_with_bad_channel_id():
    with pytest.raises(InvalidNodeException):
        node = RemoteContentNode(
            "a" * 4,
            source_node_id="b" * 32,
        )
        node.validate()


def test_remote_content_node_with_bad_source_content_node_ids():
    with pytest.raises(InvalidNodeException):
        node = RemoteContentNode(
            "a" * 32,
            source_node_id="b" * 4,
            source_content_id="c" * 4,
        )
        node.validate()


def test_remote_content_node_with_overridden_thumbnail():
    thumbimg1 = ThumbnailFile(
        path="tests/testcontent/samples/thumbnail.jpg", language="en"
    )
    remote_content_node = RemoteContentNode(
        "a" * 32,
        source_content_id="c" * 32,
        thumbnail=thumbimg1,
    )
    assert len(remote_content_node.files) == 1
    remote_content_node.validate()
    remote_content_node.process_files()
    output = remote_content_node.to_dict()
    assert output.get("files")[0]["filename"] == "d7ab03e4263fc374737d96ac2da156c1.jpg"


def test_remote_content_node_with_overridden_grade_levels():
    grades = [levels.LEVELSLIST[0], levels.LEVELSLIST[1], levels.LEVELSLIST[2]]
    remote_content_node = RemoteContentNode(
        "a" * 32,
        source_content_id="c" * 32,
        grade_levels=grades,
    )
    assert remote_content_node
    assert remote_content_node.kind == "remotecontent"
    remote_content_node.validate()
    output = remote_content_node.to_dict()
    assert output.get("grade_levels") == grades


def test_remote_content_node_with_invalid_overridden_field():
    with pytest.raises(InvalidNodeException):
        node = RemoteContentNode(
            "a" * 32,
            source_content_id="c" * 32,
            author="Such disallowed. Computer says no.",
        )
        node.validate()


def test_default_learning_activities_in_tree_node():
    node = DocumentNode(title="test", source_id="test", license=licenses.CC_BY)
    node.infer_learning_activities()
    assert node.learning_activities == [learning_activities.READ]


def test_no_default_learning_activities_in_tree_node_if_given():
    node = DocumentNode(
        title="test",
        source_id="test",
        license=licenses.CC_BY,
        learning_activities=[learning_activities.WATCH],
    )
    assert node.learning_activities != [learning_activities.READ]


def test_automatic_resource_node_video(video_file):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=video_file.path,
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    node.process_files()
    assert node.kind == content_kinds.VIDEO
    assert node.learning_activities == [learning_activities.WATCH]


def test_automatic_resource_node_audio(audio_file):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=audio_file.path,
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    node.process_files()
    assert node.kind == content_kinds.AUDIO
    assert node.learning_activities == [learning_activities.LISTEN]


def test_automatic_resource_node_document(document_file):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=document_file.path,
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    node.process_files()
    assert node.kind == content_kinds.DOCUMENT
    assert node.learning_activities == [learning_activities.READ]


@pytest.mark.parametrize("node_class", [ContentNode, DocumentNode])
def test_uri_node_failure_carries_pipeline_error(node_class):
    node = node_class(
        "test",
        "test",
        licenses.CC_BY,
        uri=sample_path("broken.pdf"),
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    with pytest.raises(InvalidNodeException, match="did not pass validation"):
        node.process_files()


def test_file_node_failure_carries_each_file_error(invalid_document_file):
    node = DocumentNode(
        "test",
        "test",
        licenses.CC_BY,
        copyright_holder="Demo Holdings",
        files=[DocumentFile(sample_path("broken.pdf")), invalid_document_file],
    )
    with pytest.raises(InvalidNodeException) as excinfo:
        node.process_files()

    message = str(excinfo.value)
    assert "did not pass validation" in message
    assert sample_path("broken.pdf") in message
    assert invalid_document_file.path in message


def test_automatic_resource_node_document_inherits_node_language(document_file):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=document_file.path,
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
        language="en",
    )
    node.process_files()
    assert all(f.language == "en" for f in node.files)


def test_content_node_passes_context_to_pipeline():
    mock_pipeline = MagicMock()
    mock_pipeline.execute.return_value = []
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri="https://www.youtube.com/watch?v=abcdefghijk",
        pipeline=mock_pipeline,
        context={"subtitle_languages": ["en", "es"]},
    )
    node._process_uri()
    mock_pipeline.execute.assert_called_once_with(
        node.uri, context={"subtitle_languages": ["en", "es"]}, skip_cache=False
    )


def test_automatic_resource_node_epub(epub_file):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=epub_file.path,
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    node.process_files()
    assert node.kind == content_kinds.DOCUMENT
    assert node.learning_activities == [learning_activities.READ]


def test_automatic_resource_node_html5(html_file):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=html_file.path,
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    node.process_files()
    assert node.kind == content_kinds.HTML5
    assert node.learning_activities == [learning_activities.EXPLORE]


def test_gather_ancestor_metadata_base_node_returns_empty_dict_with_no_metadata():
    node = Node(source_id="test", title="Test Node")
    assert node.gather_ancestor_metadata() == {}


def test_gather_ancestor_metadata_treenode_with_empty_parent_returns_empty_dict():
    node = TreeNode(source_id="test", title="Test Node")
    node.parent = Node(source_id="root", title="Test Node")
    assert node.gather_ancestor_metadata() == {}


def _assert_metadata_equal(expected, actual):
    assert set(actual.keys()) == set(expected.keys()), "Metadata keys do not match"
    for field, value in expected.items():
        if isinstance(value, list):
            assert set(actual[field]) == set(value), (
                f"Metadata for {field} does not match"
            )
        elif field == "license":
            assert actual[field].license_id == value, (
                f"Metadata for {field} does not match"
            )
        else:
            assert actual[field] == value, f"Metadata for {field} does not match"


def test_gather_ancestor_metadata_treenode_with_parent_gathers_metadata():
    parent_metadata = {
        "language": "en",
        "license": "CC BY",
        "author": "Test Author",
        "aggregator": "Test Aggregator",
        "provider": "Test Provider",
        "grade_levels": [levels.UPPER_PRIMARY],
        "resource_types": [resource_type.ACTIVITY],
        "categories": [subjects.MATHEMATICS],
        "learner_needs": [needs.INTERNET],
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = TreeNode(source_id="test", title="Test Node")
    node.parent = parent

    # Test that the node gathers metadata from its parent
    _assert_metadata_equal(parent_metadata, node.gather_ancestor_metadata())


def test_gather_ancestor_metadata_treenode_combines_own_and_parent_metadata():
    parent_metadata = {
        "language": "en",
        "license": "CC BY",
        "author": "Parent Author",
        "grade_levels": [levels.UPPER_PRIMARY],
        "resource_types": [resource_type.ACTIVITY],
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = TreeNode(
        source_id="test",
        title="Test Node",
        language="es",
        author="Child Author",
        grade_levels=[levels.LOWER_SECONDARY],
        categories=[subjects.BIOLOGY],
    )
    node.parent = parent

    expected_metadata = {
        "language": "es",  # Child's value overrides parent's
        "license": "CC BY",  # Inherited from parent
        "author": "Child Author",  # Child's value overrides parent's
        "grade_levels": [levels.LOWER_SECONDARY, levels.UPPER_PRIMARY],  # Combined list
        "resource_types": [resource_type.ACTIVITY],  # Inherited from parent
        "categories": [subjects.BIOLOGY],  # Child's value only
    }

    # Test that the node combines its own metadata with parent's
    _assert_metadata_equal(expected_metadata, node.gather_ancestor_metadata())


def test_gather_ancestor_metadata_hierarchical_metadata_merging():
    # Test that when a parent has a broader subject and child has a more specific one,
    # only the specific one is kept if the broader one is a prefix of the specific one
    parent_metadata = {
        "categories": [subjects.MATHEMATICS, subjects.SCIENCES],
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = TreeNode(
        source_id="test",
        title="Test Node",
        categories=[subjects.ALGEBRA],  # ALGEBRA is under MATHEMATICS
    )
    node.parent = parent

    result = node.gather_ancestor_metadata()

    # MATHEMATICS should be removed since ALGEBRA is a sub-subject
    # SCIENCES should be kept since it's not related to ALGEBRA
    assert subjects.MATHEMATICS not in result["categories"]
    assert subjects.ALGEBRA in result["categories"]
    assert subjects.SCIENCES in result["categories"]


def test_set_metadata_from_ancestors_contentnode_inherits_simple_fields():
    parent_metadata = {
        "language": "en",
        "license": "CC BY",
        "author": "Test Author",
        "aggregator": "Test Aggregator",
        "provider": "Test Provider",
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = ContentNode(
        source_id="test",
        title="Test Node",
        license=None,  # This should be populated from parent
    )
    node.parent = parent

    # Call the method being tested
    node.set_metadata_from_ancestors()

    # Verify the fields were properly set
    _assert_metadata_equal(parent_metadata, node.gather_ancestor_metadata())


def test_set_metadata_from_ancestors_contentnode_inherits_label_fields():
    parent_metadata = {
        "grade_levels": [levels.UPPER_PRIMARY],
        "resource_types": [resource_type.ACTIVITY],
        "categories": [subjects.MATHEMATICS],
        "learner_needs": [needs.INTERNET],
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = ContentNode(source_id="test", title="Test Node", license="CC BY")
    node.parent = parent

    # Call the method being tested
    node.set_metadata_from_ancestors()

    expected = parent_metadata.copy()
    expected["license"] = "CC BY"

    # Verify the label fields were properly set
    _assert_metadata_equal(expected, node.gather_ancestor_metadata())


def test_set_metadata_from_ancestors_contentnode_does_not_override_existing_values():
    parent_metadata = {
        "language": "en",
        "license": "CC BY",
        "author": "Parent Author",
        "grade_levels": [levels.UPPER_PRIMARY],
        "resource_types": [resource_type.ACTIVITY],
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = ContentNode(
        source_id="test",
        title="Test Node",
        license="CC BY-SA",
        language="es",
        author="Child Author",
        grade_levels=[levels.LOWER_SECONDARY],
        categories=[subjects.BIOLOGY],
    )
    node.parent = parent

    # Call the method being tested
    node.set_metadata_from_ancestors()

    # Verify that existing values were not overridden
    assert node.language == "es"
    assert node.license.license_id == "CC BY-SA"
    assert node.author == "Child Author"
    assert set(node.grade_levels) == set([levels.UPPER_PRIMARY, levels.LOWER_SECONDARY])
    assert node.categories == [subjects.BIOLOGY]

    # But non-existing values were set
    assert node.resource_types == [resource_type.ACTIVITY]


def test_set_metadata_from_ancestors_hierarchical_labels_inheritance():
    # Parent has MATHEMATICS, child has ALGEBRA
    parent_metadata = {
        "categories": [subjects.MATHEMATICS, subjects.HISTORY],
        "learner_needs": [needs.PEOPLE, needs.MATERIALS],
    }

    parent = ChannelNode(
        "parent", "www.learningequality.org", "Parent Node", **parent_metadata
    )

    node = ContentNode(
        source_id="test",
        title="Test Node",
        license="CC BY",
        categories=[subjects.ALGEBRA],  # More specific than MATHEMATICS
    )
    node.parent = parent

    node.set_metadata_from_ancestors()

    # Should only have ALGEBRA and HISTORY, not MATHEMATICS
    assert subjects.ALGEBRA in node.categories
    assert subjects.HISTORY in node.categories
    assert subjects.MATHEMATICS not in node.categories

    # Should inherit all learner needs
    assert needs.PEOPLE in node.learner_needs
    assert needs.MATERIALS in node.learner_needs


# Tests below generated using Claude 3.7 Sonnet


def test_validate_node_sets_error_attribute(channel):
    """Test that validate_node sets the _error attribute when InvalidNodeException occurs."""
    # Create a manager
    manager = ChannelManager(channel)

    # Create a mock node that will raise InvalidNodeException when validate is called
    mock_node = MagicMock()
    mock_node.validate.side_effect = InvalidNodeException("Test validation error")

    # Call validate_node with STRICT=False
    with patch("ricecooker.config.STRICT", False):
        result = manager.validate_node(mock_node)

    # Check that _error was set and validate_node returned None
    assert hasattr(mock_node, "_error")
    assert mock_node._error == "Test validation error"
    assert result is None


def test_process_node_handles_exceptions(channel):
    """Test that process_node handles InvalidNodeException and ValueError."""
    # Create a manager
    manager = ChannelManager(channel)

    # Create a mock node that will raise InvalidNodeException when process_files is called
    mock_node = MagicMock()
    mock_node.files = []
    mock_node.process_files.side_effect = InvalidNodeException("Test process error")

    # Call process_node with STRICT=False
    with patch("ricecooker.config.STRICT", False):
        result = manager.process_node(mock_node)

    # Check that _error was set and process_node returned an empty dict
    assert hasattr(mock_node, "_error")
    assert mock_node._error == "Test process error"
    assert result == {}

    # Now test with ValueError
    mock_node = MagicMock()
    mock_node.files = []
    mock_node.process_files.side_effect = ValueError("Test value error")

    # Call process_node with STRICT=False
    with patch("ricecooker.config.STRICT", False):
        result = manager.process_node(mock_node)

    # Check that _error was set and process_node returned an empty dict
    assert hasattr(mock_node, "_error")
    assert mock_node._error == "Test value error"
    assert result == {}


def test_process_node_warning_carries_pipeline_error(channel, caplog):
    node = ContentNode(
        "test",
        "test",
        licenses.CC_BY,
        uri=sample_path("broken.pdf"),
        pipeline=FilePipeline(),
        copyright_holder="Demo Holdings",
    )
    with (
        patch("ricecooker.config.STRICT", False),
        caplog.at_level(logging.WARNING, logger=config.LOGGER.name),
    ):
        ChannelManager(channel).process_node(node)

    assert any(
        r.levelno == logging.WARNING and "did not pass validation" in r.getMessage()
        for r in caplog.records
    )


def test_add_nodes_skips_invalid_nodes(channel):
    """Test that add_nodes skips invalid nodes and registers them as failed builds."""
    # Create a manager
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 10}

    # Create a valid child node
    valid_child = MagicMock()
    valid_child.valid = True
    valid_child.to_dict.return_value = {"id": "valid_id", "title": "Valid Node"}
    valid_child.get_node_id().hex = "valid_hex"

    # Create an invalid child node
    invalid_child = MagicMock()
    invalid_child.valid = False
    invalid_child.source_id = "invalid_source_id"
    invalid_child._error = "Test validation error"
    invalid_child.files = []
    invalid_child.get_node_id = MagicMock()
    invalid_child.get_node_id().hex = "invalid_hex"

    # Create a parent node with both children
    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [valid_child, invalid_child]

    # Mock the session post response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response._content = '{"root_ids": {"valid_hex": "new_root_id"}}'.encode(
        "utf-8"
    )

    # Call add_nodes
    with patch("ricecooker.config.SESSION.post", return_value=mock_response):
        manager.add_nodes("root_id", parent_node)

    # Check that the invalid node was added to failed_node_builds using its node_id.hex
    assert "invalid_hex" in manager.failed_node_builds
    assert manager.failed_node_builds["invalid_hex"]["node"] == invalid_child
    assert "Test validation error" in manager.failed_node_builds["invalid_hex"]["error"]

    # Check that only the valid node was included in the payload
    valid_child.to_dict.assert_called_once()  # valid node's to_dict was called
    invalid_child.to_dict.assert_not_called()  # invalid node's to_dict was not called


def test_add_nodes_recurses_into_siblings_of_a_skipped_last_child(channel):
    """A skipped last child must not stop its siblings' subtrees from uploading.

    Regression test for the recursion guard reading the `for child in chunk`
    loop variable after the loop, so it only ever asked whether the *last*
    child of the chunk had been created. When that child was skipped (failed
    upload or failed validation) every sibling's subtree was silently dropped.
    """
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 3}

    def make_child(node_id, valid=True, children=()):
        child = MagicMock()
        child.valid = valid
        child.files = []
        child._error = "validation error"
        child.children = list(children)
        child.to_dict.return_value = {"id": node_id}
        child.get_node_id.return_value = MagicMock(hex=node_id)
        return child

    # A valid topic owning a subtree, followed by a skipped child.
    grandchild = make_child("grandchild_hex")
    valid_topic = make_child("valid_hex", children=[grandchild])
    skipped_child = make_child("invalid_hex", valid=False)

    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [valid_topic, skipped_child]

    posted = []

    def fake_post(url, data=None, **kwargs):
        payload = json.loads(data)
        node_ids = [c["id"] for c in payload["content_data"]]
        posted.append((payload["root_id"], node_ids))
        response = MagicMock()
        response.status_code = 200
        response._content = json.dumps(
            {"root_ids": {node_id: "srv_" + node_id for node_id in node_ids}}
        ).encode("utf-8")
        return response

    with patch("ricecooker.config.SESSION.post", side_effect=fake_post):
        manager.add_nodes("root_id", parent_node)

    # The valid sibling's subtree was uploaded under the node id Studio returned.
    assert ("srv_valid_hex", ["grandchild_hex"]) in posted

    # The skipped child was reported, and never recursed into with a null parent.
    assert "invalid_hex" in manager.failed_node_builds
    assert all(root_id is not None for root_id, _ in posted)

    # Only the children actually sent are counted as uploaded.
    assert manager.node_count_dict["upload_count"] == 2


@pytest.mark.parametrize(
    "exception",
    [
        # requests' ConnectionError is not a subclass of the builtin of the same
        # name; both must reach the `except RequestException` handler.
        RequestsConnectionError("Connection refused"),
        ReadTimeout("Read timed out"),
    ],
    ids=["connection_error", "read_timeout"],
)
def test_add_nodes_handles_transport_errors(channel, exception):
    """Transport failures are recorded as batch failures, not raised."""
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 10}

    valid_child = MagicMock()
    valid_child.valid = True
    valid_child.files = []
    valid_child.to_dict.return_value = {"id": "valid_id", "title": "Valid Node"}

    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [valid_child]

    with patch("ricecooker.config.SESSION.post", side_effect=exception):
        manager.add_nodes("root_id", parent_node)

    assert "root_id" in manager.failed_node_builds
    assert manager.failed_node_builds["root_id"]["node"] == parent_node
    assert manager.failed_node_builds["root_id"]["error"] is exception
    assert manager.failed_batches == [
        {"root_id": "root_id", "node": parent_node, "error": exception}
    ]


def test_add_nodes_records_a_child_missing_from_root_ids(channel):
    """A sent child that Studio returns no id for must not be dropped quietly.

    The POST succeeds but the response carries no id for the child, so its
    subtree cannot be placed. That has to be recorded, or it is the same silent
    loss this change exists to prevent.
    """
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 2}

    child = MagicMock()
    child.valid = True
    child.files = []
    child.children = []
    child.to_dict.return_value = {"id": "sent_hex"}
    child.get_node_id.return_value = MagicMock(hex="sent_hex")

    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [child]

    # 200, but root_ids omits the child we sent.
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response._content = json.dumps({"root_ids": {}}).encode("utf-8")

    with patch("ricecooker.config.SESSION.post", return_value=mock_response):
        manager.add_nodes("root_id", parent_node)

    assert [b["root_id"] for b in manager.failed_batches] == ["sent_hex"]
    assert "sent_hex" in manager.failed_node_builds


def test_add_nodes_does_not_post_a_chunk_with_no_sendable_children(channel):
    """An all-skipped chunk carries nothing, so it must not be sent.

    Posting an empty content_data risks a non-200 turning a set of individual
    node failures into a refusal to commit the whole channel.
    """
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 1}

    skipped = MagicMock()
    skipped.valid = False
    skipped.files = []
    skipped._error = "did not validate"
    skipped.get_node_id.return_value = MagicMock(hex="skipped_hex")

    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [skipped]

    with patch("ricecooker.config.SESSION.post") as post:
        manager.add_nodes("root_id", parent_node)

    post.assert_not_called()
    # Reported as an individual node, and the channel can still be committed.
    assert "skipped_hex" in manager.failed_node_builds
    assert manager.failed_batches == []


def test_check_failed_logs_the_response_body_for_a_batch_failure(channel, caplog):
    """Studio's response body has to reach the operator.

    The HTTP reason phrase is the same for every 500; the body is the only
    thing that distinguishes one from another.
    """
    manager = ChannelManager(channel)
    manager._record_failed_batch(
        "root_id",
        MagicMock(),
        "Internal Server Error",
        content=b"node 4821 rejected, bad license id",
    )

    with caplog.at_level(logging.ERROR, logger=config.LOGGER.name):
        manager.check_failed()

    assert "Internal Server Error" in caplog.text
    assert "node 4821 rejected" in caplog.text


def test_upload_tree_refuses_to_commit_when_a_node_batch_failed(channel):
    """A whole add_nodes request failing must block the commit.

    An individual bad node is reported and the channel still ships, but a batch
    that never landed takes every descendant with it, so committing would stage
    a channel with subtrees silently missing.
    """
    child = TopicNode("topic", "Topic")
    channel.add_child(child)
    for node in (channel, child):
        node.valid = True

    manager = ChannelManager(channel)

    def fake_post(url, **kwargs):
        response = MagicMock()
        if url == config.add_nodes_url():
            raise RequestsConnectionError("Connection reset by peer")
        response.status_code = 200
        response._content = json.dumps(
            {"root": "root", "channel_id": "chan-id", "new_channel": "chan-id"}
        ).encode("utf-8")
        return response

    with patch("ricecooker.config.SESSION.post", side_effect=fake_post) as post:
        with pytest.raises(ChannelIncompleteError):
            manager.upload_tree()

    assert [b["root_id"] for b in manager.failed_batches] == ["root"]
    # The commit endpoint must never have been called.
    assert all(
        call.args[0] != config.finish_channel_url() for call in post.call_args_list
    )


def test_upload_tree_still_commits_when_only_one_node_failed(channel):
    """A single node with a failed file is reported but must not block the commit."""
    good = TopicNode("good", "Good")
    bad = DocumentNode(
        "bad", "Bad", license=get_license(licenses.CC_BY, copyright_holder="x")
    )
    bad_file = MagicMock()
    bad_file.is_primary = True
    bad_file.filename = "bad.pdf"
    bad_file.to_dict.return_value = {"filename": "bad.pdf", "preset": "document"}
    bad.files = [bad_file]
    channel.add_child(good)
    channel.add_child(bad)
    for node in (channel, good, bad):
        node.valid = True

    manager = ChannelManager(channel)
    # bad.pdf's upload to Studio failed and survived the retry.
    manager.failed_uploads = {"bad.pdf": "500 Server Error"}

    committed = []

    def fake_post(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        if url == config.add_nodes_url():
            payload = json.loads(kwargs["data"])
            response._content = json.dumps(
                {
                    "root_ids": {
                        c["node_id"]: "srv_" + c["node_id"]
                        for c in payload["content_data"]
                    }
                }
            ).encode("utf-8")
        else:
            committed.append(url)
            response._content = json.dumps(
                {"root": "root", "channel_id": "chan-id", "new_channel": "chan-id"}
            ).encode("utf-8")
        return response

    with patch("ricecooker.config.SESSION.post", side_effect=fake_post):
        manager.upload_tree()

    assert manager.failed_batches == []
    assert bad.get_node_id().hex in manager.failed_node_builds
    assert config.finish_channel_url() in committed


def test_failed_question_image_skips_only_its_exercise(channel, exercise_image_file):
    _clear_ricecookerfilecache()

    def exercise(source_id, image_url):
        return ExerciseNode(
            source_id,
            source_id,
            license=get_license(licenses.CC_BY, copyright_holder="x"),
            exercise_data={"m": 1, "n": 1},
            questions=[
                SingleSelectQuestion(
                    source_id + "-q", "Q", "a", ["a", "b"], hints=[f"![]({image_url})"]
                )
            ],
        )

    good = exercise("good", "http://h/present.png")
    bad = exercise("bad", "http://h/missing.png")
    channel.add_child(good)
    channel.add_child(bad)
    with open(exercise_image_file.path, "rb") as f:
        png = f.read()

    manager = ChannelManager(channel)
    with (
        patch("ricecooker.config.STRICT", False),
        fake_download_session({"http://h/present.png": png}),
    ):
        manager.validate()
        manager.process_tree()

    manager.root_id, manager.channel_id = "root", "chan-id"
    posted = []
    with patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)):
        manager.upload_tree()
    assert [child["source_id"] for _, child in posted] == ["good"]
    error = manager.failed_node_builds[bad.get_node_id().hex]["error"]
    assert "http://h/missing.png" in error


@pytest.mark.parametrize("threads", [1, 5])
@pytest.mark.parametrize("strict", [True, False])
def test_question_shared_by_two_exercises_uploads_both(
    channel, exercise_image_file, strict, threads
):
    _clear_ricecookerfilecache()
    urls = {n: f"http://h/{n}.png" for n in "qah"}
    q = SingleSelectQuestion(
        "q1",
        f"![]({urls['q']})",
        f"![]({urls['a']})",
        [f"![]({urls['a']})", "b"],
        hints=[f"![]({urls['h']})", f"![]({urls['q']})"],
    )
    for source_id in ("ex1", "ex2"):
        channel.add_child(
            ExerciseNode(
                source_id,
                source_id,
                license=get_license(licenses.CC_BY, copyright_holder="x"),
                exercise_data={"m": 1, "n": 1},
                questions=[q],
            )
        )
    with open(exercise_image_file.path, "rb") as f:
        png = f.read()

    manager = ChannelManager(channel)
    with (
        patch("ricecooker.config.STRICT", strict),
        patch("ricecooker.config.TASK_THREADS", threads),
        fake_download_session({url: png for url in urls.values()}),
    ):
        manager.validate()
        manager.process_tree()

    manager.root_id, manager.channel_id = "root", "chan-id"
    posted = []
    with patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)):
        manager.upload_tree()
    assert [child["source_id"] for _, child in posted] == ["ex1", "ex2"]
    for _, child in posted:
        (item,) = child["questions"]
        assert sorted(f["original_filename"] for f in item["files"]) == [
            "a.png",
            "h.png",
            "q.png",
        ]


def test_perseus_question_shared_by_two_exercises_lists_image_once_each(
    channel, exercise_image_file
):
    _clear_ricecookerfilecache()
    q = PerseusQuestion(
        "q1",
        json.dumps({"question": {"content": "![](http://h/q.png)"}}),
        ka_language="en",
    )
    for source_id in ("ex1", "ex2"):
        channel.add_child(
            ExerciseNode(
                source_id,
                source_id,
                license=get_license(licenses.CC_BY, copyright_holder="x"),
                exercise_data={"m": 1, "n": 1},
                questions=[q],
            )
        )
    with open(exercise_image_file.path, "rb") as f:
        png = f.read()

    manager = ChannelManager(channel)
    with (
        patch("ricecooker.config.TASK_THREADS", 5),
        fake_download_session({"http://h/q.png": png}),
    ):
        manager.validate()
        manager.process_tree()

    manager.root_id, manager.channel_id = "root", "chan-id"
    posted = []
    with patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)):
        manager.upload_tree()
    assert [child["source_id"] for _, child in posted] == ["ex1", "ex2"]
    for _, child in posted:
        (item,) = child["questions"]
        assert [f["original_filename"] for f in item["files"]] == ["q.png"]


def test_failed_question_shared_between_exercises_drops_only_its_exercises(
    channel, exercise_image_file
):
    _clear_ricecookerfilecache()
    good = SingleSelectQuestion("good", "![](http://h/q.png)", "a", ["a", "b"])
    bad = SingleSelectQuestion("bad", "![](http://h/missing.png)", "a", ["a", "b"])
    for source_id, questions in (
        ("e1", [bad, good]),
        ("e2", [good]),
        ("e3", [bad]),
    ):
        channel.add_child(
            ExerciseNode(
                source_id,
                source_id,
                license=get_license(licenses.CC_BY, copyright_holder="x"),
                exercise_data={"m": 1, "n": 1},
                questions=questions,
            )
        )
    with open(exercise_image_file.path, "rb") as f:
        png = f.read()

    manager = ChannelManager(channel)
    with (
        patch("ricecooker.config.STRICT", False),
        fake_download_session({"http://h/q.png": png}),
    ):
        manager.validate()
        manager.process_tree()

    manager.root_id, manager.channel_id = "root", "chan-id"
    posted = []
    with patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)):
        manager.upload_tree()
    assert [child["source_id"] for _, child in posted] == ["e2"]
    (item,) = posted[0][1]["questions"]
    assert [f["original_filename"] for f in item["files"]] == ["q.png"]


@pytest.mark.parametrize("threads", [1, 5])
def test_exercise_cloned_under_two_topics_uploads_every_placement(
    channel, exercise_image_file, threads
):
    _clear_ricecookerfilecache()
    q = SingleSelectQuestion(
        "q1", "![](http://h/q.png)", "a", ["a", "b"], hints=["![](http://h/h.png)"]
    )
    ex = ExerciseNode(
        "ex1",
        "ex1",
        license=get_license(licenses.CC_BY, copyright_holder="x"),
        exercise_data={"m": 1, "n": 1},
        questions=[q],
    )
    for source_id in ("t1", "t2"):
        topic = TopicNode(source_id, source_id)
        channel.add_child(topic)
        topic.add_child(ex)
    with open(exercise_image_file.path, "rb") as f:
        png = f.read()

    manager = ChannelManager(channel)
    manager.deduplicate_shared_nodes()
    with (
        patch("ricecooker.config.STRICT", True),
        patch("ricecooker.config.TASK_THREADS", threads),
        fake_download_session({"http://h/q.png": png, "http://h/h.png": png}),
    ):
        manager.validate()
        manager.process_tree()

    manager.root_id, manager.channel_id = "root", "chan-id"
    posted = []
    with patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)):
        manager.upload_tree()
    exercises = [child for _, child in posted if child["source_id"] == "ex1"]
    assert len(exercises) == 2
    for child in exercises:
        (item,) = child["questions"]
        assert sorted(f["original_filename"] for f in item["files"]) == [
            "h.png",
            "q.png",
        ]


@pytest.mark.parametrize(
    "original_filename",
    ["a" * 296 + ".pdf", "a" * 254],
    ids=["300_with_extension", "254_without_extension"],
)
def test_file_with_overlong_original_filename_uploads(
    tree, document, original_filename
):
    manager = ChannelManager(tree)
    manager.root_id, manager.channel_id = "root", "chan-id"
    manager.validate()
    files = manager.process_tree()
    doc_file = next(f for f in document.files if isinstance(f, DocumentFile))
    doc_file.original_filename = original_filename

    upload_names = {}
    added_node_ids = []

    def fake_post(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        if url == config.get_upload_url():
            name = kwargs["json"]["name"]
            upload_names[kwargs["json"]["checksum"]] = name
            if len(name) > config.MAX_ORIGINAL_FILENAME_LENGTH:
                response.status_code = 500
                return response
            response.json.return_value = {
                "uploadURL": "https://storage.test/upload",
                "mimetype": "application/pdf",
                "might_skip": False,
            }
        elif url == config.add_nodes_url():
            payload = json.loads(kwargs["data"])
            added_node_ids.extend(c["node_id"] for c in payload["content_data"])
            response._content = json.dumps(
                {
                    "root_ids": {
                        c["node_id"]: "srv_" + c["node_id"]
                        for c in payload["content_data"]
                    }
                }
            ).encode("utf-8")
        else:
            response._content = json.dumps(
                {"root": "root", "channel_id": "chan-id", "new_channel": "chan-id"}
            ).encode("utf-8")
        return response

    with (
        patch("ricecooker.config.SESSION.post", side_effect=fake_post),
        patch("ricecooker.config.SESSION.put", return_value=MagicMock(status_code=200)),
    ):
        manager.upload_files(files)
        manager.reattempt_upload_fails()
        manager.upload_tree()

    assert manager.failed_uploads == {}
    node_id = document.get_node_id().hex
    assert node_id in added_node_ids
    doc_name = upload_names[doc_file.checksum]
    assert len(doc_name) <= config.MAX_ORIGINAL_FILENAME_LENGTH
    assert doc_name.endswith(".pdf")


def test_leftover_perseus_graphie_blocks_upload(channel, mastery_model):
    exercise = ExerciseNode(
        "exercise",
        "Exercise",
        license=get_license(licenses.CC_BY, copyright_holder="x"),
        exercise_data=mastery_model,
        questions=[
            PerseusQuestion(
                "q1",
                r'{"question": {"content": "[link](web+graphie:\/\/h\/x)"}}',
                ka_language="en",
            )
        ],
    )
    channel.add_child(exercise)
    manager = ChannelManager(channel)
    manager.root_id, manager.channel_id = "root", "chan-id"
    sent = []

    def fake_post(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        payload = json.loads(kwargs["data"]) if url == config.add_nodes_url() else {}
        sent.extend(c["node_id"] for c in payload.get("content_data", []))
        response._content = json.dumps(
            {
                "root_ids": {n: "srv_" + n for n in sent},
                "root": "root",
                "channel_id": "chan-id",
                "new_channel": "chan-id",
            }
        ).encode("utf-8")
        return response

    with (
        patch("ricecooker.config.STRICT", False),
        patch("ricecooker.config.SESSION.post", side_effect=fake_post),
    ):
        manager.validate()
        manager.process_tree()
        manager.upload_tree()

    node_id = exercise.get_node_id().hex
    assert node_id not in sent
    assert "web+graphie://" in manager.failed_node_builds[node_id]["error"]


def test_add_nodes_handles_server_error(channel):
    """Test that add_nodes handles server error responses."""
    # Create a manager
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 10}

    # Create a valid child node
    valid_child = MagicMock()
    valid_child.valid = True
    valid_child.to_dict.return_value = {"id": "valid_id", "title": "Valid Node"}

    # Create a parent node with the child
    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [valid_child]

    # Mock the session post to return a 500 error
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.reason = "Internal Server Error"
    mock_response.content = b"Server error"

    with patch("ricecooker.config.SESSION.post", return_value=mock_response):
        manager.add_nodes("root_id", parent_node)

    # Check that the error was registered in failed_node_builds
    assert "root_id" in manager.failed_node_builds
    assert manager.failed_node_builds["root_id"]["node"] == parent_node
    assert manager.failed_node_builds["root_id"]["error"] == "Internal Server Error"
    # A non-200 loses every node under root_id, so it is a batch failure.
    assert [b["root_id"] for b in manager.failed_batches] == ["root_id"]
    assert manager.failed_node_builds["root_id"]["content"] == b"Server error"
    # check_failed() reads the body off the batch entry, so pin it there too.
    assert manager.failed_batches[0]["content"] == b"Server error"


def test_file_upload_insufficient_storage(channel):
    """Test that do_file_upload raises InsufficientStorageException on 412 response."""
    # Create a manager
    manager = ChannelManager(channel)

    # Mock file_map, get_storage_path, and file open
    filename = "test_file.mp4"
    file_data = MagicMock()
    file_data.skip_upload = False
    file_data.size = 1024
    file_data.checksum = "abcdef1234567890"
    file_data.original_filename = None
    file_data.get_filename.return_value = filename
    file_data.extension = "mp4"
    file_data.get_preset.return_value = "video"
    file_data.duration = 60

    manager.file_map = {filename: file_data}

    # Mock the open call
    mocked_open = mock_open(read_data=b"test file content")

    # Mock the session post to return a 412 error
    mock_response = MagicMock()
    mock_response.status_code = 412

    with (
        patch("builtins.open", mocked_open),
        patch("ricecooker.config.get_storage_path", return_value="/tmp/test_file.mp4"),
        patch("ricecooker.config.os.path.isfile", return_value=True),
        patch("ricecooker.config.SESSION.post", return_value=mock_response),
    ):
        # Check that InsufficientStorageException is raised
        with pytest.raises(
            InsufficientStorageException, match="You have run out of storage space."
        ):
            manager.do_file_upload(filename)


def test_file_upload_missing_storage_raises_descriptive_error(channel):
    """do_file_upload reports a cache/storage mismatch instead of a bare FileNotFoundError."""
    manager = ChannelManager(channel)

    filename = "0123456789abcdef0123456789abcdef.mp4"
    file_data = MagicMock()
    file_data.skip_upload = False
    manager.file_map = {filename: file_data}

    storage_path = config.get_storage_path(filename)
    assert not os.path.isfile(storage_path)
    with pytest.raises(FileNotFoundException) as exc_info:
        manager.do_file_upload(filename)
    assert storage_path in str(exc_info.value)


@pytest.mark.parametrize(
    "original_filename, expected",
    [
        ("Chapter 1.2 Intro.pdf", "Chapter 1.2 Intro.pdf"),
        ("Chapter 1.2 Intro", "Chapter 1.2 Intro.pdf"),
        ("Report.PDF", "Report.PDF"),
    ],
)
def test_file_upload_name_keeps_dotted_stem(studio, original_filename, expected):
    document = DocumentFile(sample_path("sample_doc_with_toc.pdf"))
    channel = ChannelNode("dotted", "www.learningequality.org", "Dotted")
    channel.add_child(
        DocumentNode(
            "doc",
            "Doc",
            license=get_license(licenses.CC_BY, copyright_holder="x"),
            files=[document],
        )
    )
    manager = ChannelManager(channel)
    filenames = manager.process_tree()
    # Transfers such as Google Drive name files without an extension.
    document.original_filename = original_filename

    manager.upload_files(filenames)

    assert studio.upload_names == [expected]


def test_file_upload_name_replaces_converted_extension(studio, tmp_path):
    cover = str(tmp_path / "Cover 1.2.webp")
    Image.open(sample_path("thumbnail.png")).save(cover)
    channel = ChannelNode("converted", "www.learningequality.org", "Converted")
    channel.add_child(
        DocumentNode(
            "document",
            "Document",
            license=get_license(licenses.CC_BY, copyright_holder="x"),
            thumbnail=cover,
            files=[DocumentFile(sample_path("41568-pdf.pdf"))],
        )
    )
    channel.add_child(
        VideoNode(
            "video",
            "Video",
            license=get_license(licenses.CC_BY, copyright_holder="x"),
            files=[
                VideoFile(sample_path("sample.mov")),
                SubtitleFile(sample_path("testsubtitles_ar.srt"), language="ar"),
            ],
        )
    )
    manager = ChannelManager(channel)

    manager.upload_files(manager.process_tree())

    assert sorted(studio.upload_names) == [
        "41568-pdf.pdf",
        "Cover 1.2.png",
        "sample.webm",
        "testsubtitles_ar.vtt",
    ]


def test_add_nodes_checks_both_failed_files_and_validity(channel):
    """Test that add_nodes checks both for failed files and node validity."""
    # Create a manager
    manager = ChannelManager(channel)
    manager.node_count_dict = {"upload_count": 0, "total_count": 10}

    # Create three types of nodes:
    # 1. Valid node with no failed files
    valid_node = MagicMock()
    valid_node.valid = True
    valid_node.files = []
    valid_node.to_dict.return_value = {"id": "valid"}
    valid_node.get_node_id = MagicMock()
    valid_node.get_node_id().hex = "valid-hex"

    # 2. Valid node with a failed file
    node_with_failed_file = MagicMock()
    node_with_failed_file.valid = True
    failed_file = MagicMock()
    failed_file.is_primary = True
    failed_file.filename = None  # Failed to download
    node_with_failed_file.files = [failed_file]
    node_with_failed_file.get_node_id = MagicMock()
    node_with_failed_file.get_node_id().hex = "failed-file-hex"

    # 3. Invalid node with no failed files
    invalid_node = MagicMock()
    invalid_node.valid = False
    invalid_node.files = []
    invalid_node.get_node_id = MagicMock()
    invalid_node.get_node_id().hex = "invalid-hex"
    invalid_node._error = "Validation error"

    # Create parent with all test nodes
    parent_node = MagicMock()
    parent_node.title = "Parent"
    parent_node.children = [valid_node, node_with_failed_file, invalid_node]

    # Mock the session post response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response._content = '{"root_ids": {"valid-hex": "new-root-id"}}'.encode(
        "utf-8"
    )

    # Call add_nodes
    with patch("ricecooker.config.SESSION.post", return_value=mock_response):
        manager.add_nodes("root_id", parent_node)

    # Check that both types of failed nodes were registered in failed_node_builds
    assert "failed-file-hex" in manager.failed_node_builds  # Node with failed file
    assert "invalid-hex" in manager.failed_node_builds  # Invalid node

    # Check that only the valid node was included in the payload
    valid_node.to_dict.assert_called_once()
    node_with_failed_file.to_dict.assert_not_called()
    invalid_node.to_dict.assert_not_called()


# End generated tests


""" *********** NODE COPY / DEDUP TESTS (issue #354) *********** """


def _place_under_two_topics(channel, node):
    """Add ``node`` under two sibling topics of ``channel``; return the topics."""
    t1, t2 = TopicNode("t1", "T1"), TopicNode("t2", "T2")
    channel.add_child(t1)
    channel.add_child(t2)
    t1.add_child(node)
    t2.add_child(node)
    return t1, t2


def test_copy_resets_ids_and_parent(channel, topic, document):
    channel.add_child(topic)
    topic.add_child(document)
    document.get_node_id()  # materialize + cache node_id/content_id on the original
    clone = document.copy()
    assert clone is not document
    assert clone.parent is None
    assert clone.node_id is None
    assert clone.content_id is None
    assert clone.source_id == document.source_id


def test_copy_shares_file_objects(document):
    clone = document.copy()
    assert clone.files is not document.files  # new list container
    assert set(map(id, clone.files)) == set(
        map(id, document.files)
    )  # same File objects
    assert (
        clone.thumbnail is document.thumbnail
    )  # thumbnail object shared too (decision #1)


def test_copy_clones_children_recursively(topic, document):
    topic.add_child(document)
    clone = topic.copy()
    assert clone.children[0] is not document
    assert clone.children[0].parent is clone
    assert clone.children[0].source_id == document.source_id


def test_dedup_clones_cross_parent_reuse(channel, document):
    t1, t2 = _place_under_two_topics(channel, document)  # same object, two parents
    ChannelManager(channel).deduplicate_shared_nodes()
    placed1, placed2 = t1.children[0], t2.children[0]
    assert placed1 is not placed2
    assert (
        placed1.parent is t1 and placed2.parent is t2
    )  # kept placement's parent repaired (construction left it pointing at t2)
    assert placed1.get_content_id() == placed2.get_content_id()  # shared content_id
    assert placed1.get_node_id() != placed2.get_node_id()  # distinct node_id


def test_dedup_shares_file_objects(channel, document):
    t1, t2 = _place_under_two_topics(channel, document)
    ChannelManager(channel).deduplicate_shared_nodes()
    original_file_ids = set(map(id, t1.children[0].files))
    assert set(map(id, t2.children[0].files)) == original_file_ids  # same File objects


def test_dedup_clones_shared_subtree(channel, document):
    shared = TopicNode("shared", "Shared")
    shared.add_child(document)
    t1, t2 = _place_under_two_topics(channel, shared)  # same subtree, two parents
    ChannelManager(channel).deduplicate_shared_nodes()
    s1, s2 = t1.children[0], t2.children[0]
    assert s1 is not s2
    assert s1.children[0] is not s2.children[0]  # descendants cloned too
    assert s1.children[0].get_node_id() != s2.children[0].get_node_id()
    assert s1.children[0].get_content_id() == s2.children[0].get_content_id()


def test_dedup_no_spurious_clone(channel, document):
    t1 = TopicNode("t1", "T1")
    channel.add_child(t1)
    t1.add_child(document)
    original = t1.children[0]
    ChannelManager(channel).deduplicate_shared_nodes()
    assert t1.children[0] is original  # untouched when not reused


def test_dedup_preserves_same_parent_error(channel, document):
    t1 = TopicNode("t1", "T1")
    channel.add_child(t1)
    t1.add_child(document)
    t1.add_child(document)  # same object twice under ONE parent
    manager = ChannelManager(channel)
    manager.deduplicate_shared_nodes()
    assert len(t1.children) == 2 and t1.children[0] is t1.children[1]  # not cloned
    with patch("ricecooker.config.STRICT", True):
        with pytest.raises(InvalidNodeException):
            manager.validate()


def test_create_initial_tree_deduplicates_reused_node(channel, document):
    from ricecooker.commands import create_initial_tree

    t1, t2 = _place_under_two_topics(channel, document)
    create_initial_tree(channel)
    assert t1.children[0].get_node_id() != t2.children[0].get_node_id()


def test_rejected_studio_token_exits_nonzero():
    from ricecooker.commands import authenticate_user

    rejected = requests.Response()
    rejected.status_code = 401
    with (
        patch.dict(config.SESSION.headers),
        patch("ricecooker.config.SESSION.post", return_value=rejected),
    ):
        with pytest.raises(SystemExit) as exited:
            authenticate_user("bad-token")
    assert exited.value.code not in (None, 0)


def _studio_response(status_code, body=None):
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(body).encode("utf-8")
    return response


class FakeStudio:
    def __init__(self):
        self.editable = True
        self.thumbnail = None
        self.stored = set()
        self.upload_names = []
        self.failing_formats = set()

    def post(self, url, data=None, **kwargs):
        payload = kwargs.get("json") or json.loads(data or "{}")
        if url == config.authentication_url():
            return _studio_response(200, {"username": "chef"})
        if url == config.check_version_url():
            return _studio_response(200, {"status": 0, "message": ""})
        if url == config.create_channel_url():
            if not self.editable:
                # create_channel's SuspiciousOperation surfaces as a 500.
                return _studio_response(500, "Internal server error")
            channel_data = payload["channel_data"]
            self.thumbnail = channel_data["thumbnail"]
            return _studio_response(
                200, {"root": "root", "channel_id": channel_data["id"]}
            )
        if url == config.get_upload_url():
            self.upload_names.append(payload["name"])
            upload_url = "https://storage.test/{checksum}.{file_format}".format(
                **payload
            )
            return _studio_response(
                200,
                {
                    "uploadURL": upload_url,
                    "mimetype": "application/octet-stream",
                    "might_skip": False,
                },
            )
        if url == config.add_nodes_url():
            node_ids = [node["node_id"] for node in payload["content_data"]]
            return _studio_response(
                200, {"root_ids": {n: "srv_" + n for n in node_ids}}
            )
        if url == config.finish_channel_url():
            return _studio_response(200, {"new_channel": payload["channel_id"]})
        raise AssertionError("unexpected Studio call: " + url)

    def put(self, url, **kwargs):
        name = url.rsplit("/", 1)[-1]
        if name.rsplit(".", 1)[-1] in self.failing_formats:
            return _studio_response(500, "Internal server error")
        self.stored.add(name)
        return _studio_response(200)

    def head(self, url, **kwargs):
        return _studio_response(200 if url.rsplit("/", 1)[-1] in self.stored else 404)


@pytest.fixture
def studio(monkeypatch):
    fake = FakeStudio()
    for name in ("SESSION", "DOWNLOAD_SESSION"):
        session = requests.Session()
        session.post, session.put, session.head = fake.post, fake.put, fake.head
        monkeypatch.setattr(config, name, session)
    return fake


class ThumbnailChef(SushiChef):
    auth = None
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "testing.learningequality.org",
        "CHANNEL_SOURCE_ID": "thumbnail-chef",
        "CHANNEL_TITLE": "Thumbnail chef",
        "CHANNEL_LANGUAGE": "en",
        "CHANNEL_THUMBNAIL": sample_path("thumbnail.png"),
    }

    def construct_channel(self, **kwargs):
        self.channel = self.get_channel(**kwargs)
        self.channel.add_child(
            DocumentNode(
                "doc",
                "Doc",
                license=get_license(licenses.CC_BY, copyright_holder="x"),
                files=[DocumentFile(sample_path("sample_doc_with_toc.pdf"))],
            )
        )
        return self.channel


@pytest.fixture
def chef(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in (
        "UPDATE",
        "VIDEO_HEIGHT",
        "THUMBNAILS",
        "STAGE",
        "PUBLISH",
        "FILE_PIPELINE",
    ):
        monkeypatch.setattr(config, name, getattr(config, name))
    return ThumbnailChef()


@pytest.mark.parametrize("reupload", [False, True], ids=["new", "reupload"])
def test_upload_leaves_channel_thumbnail_on_studio(chef, studio, reupload):
    if reupload:
        uploadchannel(ThumbnailChef(), token="tok")
    uploadchannel(chef, token="tok")

    assert studio.thumbnail == chef.channel.thumbnail.filename
    assert studio.thumbnail in studio.stored


def test_upload_omits_channel_thumbnail_that_failed_to_upload(chef, studio):
    studio.failing_formats.add("png")
    uploadchannel(chef, token="tok")

    assert studio.thumbnail is None


def test_channel_without_edit_rights_fails_before_any_download(chef, studio):
    studio.editable = False
    with pytest.raises(SystemExit) as exited:
        uploadchannel(chef, token="tok")

    assert exited.value.code not in (None, 0)
    nodes = [chef.channel] + chef.channel.children
    assert all(f.filename is None for node in nodes for f in node.files)


""" *********** INVALID METADATA TESTS (issue #782) *********** """


def _fake_studio_post(posted):
    def fake_post(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        if url == config.add_nodes_url():
            payload = json.loads(kwargs["data"])
            children = payload["content_data"]
            posted.extend((payload["root_id"], child) for child in children)
            body = {"root_ids": {c["node_id"]: "srv_" + c["node_id"] for c in children}}
        else:
            body = {"root": "root", "channel_id": "chan-id", "new_channel": "chan-id"}
        response._content = json.dumps(body).encode("utf-8")
        return response

    return fake_post


def _upload_beside_a_kept_topic(channel, caplog, dropped):
    channel.add_child(dropped)
    channel.add_child(TopicNode("kept", "Kept"))
    manager = ChannelManager(channel)
    with patch("ricecooker.config.STRICT", False):
        manager.validate()
        manager.process_tree()
    caplog.clear()
    posted = []
    with (
        patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)),
        caplog.at_level(logging.WARNING, logger=config.LOGGER.name),
    ):
        manager.upload_tree()
    assert [child["source_id"] for _, child in posted] == ["kept"]
    return [r.getMessage() for r in caplog.records if dropped.title in r.getMessage()]


@pytest.mark.parametrize(
    "node_class, reason",
    [
        (ContentNode, "No kind has been set"),
        (ExerciseNode, "Exercise does not have any questions"),
    ],
    ids=["no_files", "no_questions"],
)
def test_upload_tree_summary_names_each_dropped_node(
    channel, caplog, node_class, reason
):
    dropped = node_class(
        "dropped", "Dropped", license=get_license(licenses.CC_BY, copyright_holder="x")
    )
    summary = _upload_beside_a_kept_topic(channel, caplog, dropped)
    assert summary == ["\t{}: {}".format(dropped, reason)]


def test_upload_tree_drops_a_node_whose_processing_raised(channel, caplog):
    dropped = ContentNode(
        "subs",
        "Subs",
        license=get_license(licenses.CC_BY, copyright_holder="x"),
        uri=sample_path("testsubtitles_ar.srt"),
        pipeline=FilePipeline(),
    )
    summary = _upload_beside_a_kept_topic(channel, caplog, dropped)
    assert len(summary) == 1
    assert summary[0].startswith("\t{}: Missing required context".format(dropped))


def _pdf_as(node_class):
    kwargs = (
        {"questions": [SingleSelectQuestion("q1", "Q", "A", ["A"])]}
        if node_class is ExerciseNode
        else {}
    )
    return node_class(
        "mismatch",
        "Mismatch",
        license=get_license(licenses.CC_BY, copyright_holder="x"),
        uri=sample_path("41568-pdf.pdf"),
        pipeline=FilePipeline(),
        **kwargs,
    )


@pytest.mark.parametrize("node_class", [VideoNode, ExerciseNode])
def test_upload_tree_drops_a_node_whose_uri_infers_another_kind(
    channel, caplog, node_class
):
    dropped = _pdf_as(node_class)
    summary = _upload_beside_a_kept_topic(channel, caplog, dropped)
    assert summary == [
        "\t{}: Inferred kind is different from content node class kind.".format(dropped)
    ]


@pytest.mark.parametrize("node_class", [VideoNode, ExerciseNode])
def test_process_tree_raises_on_a_kind_mismatch_in_strict_mode(channel, node_class):
    channel.add_child(_pdf_as(node_class))
    with (
        patch("ricecooker.config.STRICT", True),
        pytest.raises(InvalidNodeException, match="Inferred kind is different"),
    ):
        ChannelManager(channel).process_tree()


def test_upload_tree_keeps_a_topic_whose_tag_was_dropped(channel, caplog):
    long_tag = "t" * 31
    topic = TopicNode("tagged", "Tagged", tags=["short", long_tag])
    topic.add_child(TopicNode("child", "Child"))
    channel.add_child(topic)
    manager = ChannelManager(channel)
    posted = []
    with (
        patch("ricecooker.config.STRICT", False),
        patch("ricecooker.config.SESSION.post", side_effect=_fake_studio_post(posted)),
        caplog.at_level(logging.WARNING, logger=config.LOGGER.name),
    ):
        manager.validate()
        manager.process_tree()
        manager.upload_tree()

    assert [(root_id, c["source_id"], c["tags"]) for root_id, c in posted] == [
        ("root", "tagged", ["short"]),
        ("srv_" + topic.get_node_id().hex, "child", []),
    ]
    assert any(
        r.levelno == logging.WARNING
        and "tagged" in r.getMessage()
        and long_tag in r.getMessage()
        for r in caplog.records
    )


CLEANABLE_VALUES = [
    ("tags", "short", "t" * 31),
    ("tags", "short", 7),
    ("grade_levels", levels.LOWER_SECONDARY, "not-a-label"),
    ("resource_types", resource_type.LESSON, "not-a-label"),
    ("learning_activities", learning_activities.WATCH, "not-a-label"),
    (
        "accessibility_labels",
        accessibility_categories.CAPTIONS_SUBTITLES,
        "not-a-label",
    ),
    ("categories", subjects.BIOLOGY, "not-a-label"),
    ("learner_needs", needs.MATERIALS, "not-a-label"),
]


@pytest.mark.parametrize("field, valid, invalid", CLEANABLE_VALUES)
def test_validate_drops_an_invalid_metadata_value(channel, field, valid, invalid):
    node = TopicNode("topic", "Topic", **{field: [valid, invalid]})
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", False):
        ChannelManager(channel).validate()
    assert (node.valid, getattr(node, field)) == (True, [valid])


def test_process_tree_keeps_a_content_node_whose_tag_was_dropped(channel):
    node = ContentNode(
        "doc",
        "Doc",
        license=get_license(licenses.CC_BY, copyright_holder="x"),
        uri=sample_path("sample_doc_with_toc.pdf"),
        pipeline=FilePipeline(),
        tags=["short", "t" * 31],
    )
    channel.add_child(node)
    manager = ChannelManager(channel)
    with patch("ricecooker.config.STRICT", False):
        manager.validate()
        manager.process_tree()
    assert (node.valid, node.tags) == (True, ["short"])


def test_remote_content_node_sends_the_tags_left_after_validation(channel):
    node = RemoteContentNode(
        "a" * 32, source_content_id="c" * 32, tags=["short", "t" * 31]
    )
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", False):
        ChannelManager(channel).validate()
    assert node.to_dict()["tags"] == ["short"]


def test_dropped_label_warning_names_node_field_and_value(channel, caplog):
    node = TopicNode("topic", "Topic", categories=[subjects.BIOLOGY, "bogus"])
    channel.add_child(node)
    with (
        patch("ricecooker.config.STRICT", False),
        caplog.at_level(logging.WARNING, logger=config.LOGGER.name),
    ):
        ChannelManager(channel).validate()
    assert [r.getMessage() for r in caplog.records] == [
        f"{node}: Invalid categories value 'bogus'. Dropped it."
    ]


@pytest.mark.parametrize("container", [list, tuple])
def test_validate_drops_an_over_long_new_tag_with_a_warning(channel, caplog, container):
    long_tag = "t" * 31
    node = TopicNode(
        "topic",
        "Topic",
        node_modifications={"New Tags": container(["short", long_tag, "s2"])},
    )
    channel.add_child(node)
    with (
        patch("ricecooker.config.STRICT", False),
        caplog.at_level(logging.WARNING, logger=config.LOGGER.name),
    ):
        # Re-validated as ContentNode.process_files() does; warns once.
        ChannelManager(channel).validate()
        ChannelManager(channel).validate()
    assert (node.valid, node.to_dict()["tags"]) == (True, ["short", "s2"])
    (record,) = caplog.records
    assert "(topic):" in record.getMessage() and long_tag in record.getMessage()


def test_validate_raises_on_an_over_long_new_tag_in_strict_mode(channel):
    long_tag = "t" * 31
    node = TopicNode("topic", "Topic", node_modifications={"New Tags": [long_tag]})
    channel.add_child(node)
    with (
        patch("ricecooker.config.STRICT", True),
        pytest.raises(InvalidNodeException) as raised,
    ):
        ChannelManager(channel).validate()
    assert str(raised.value).startswith(f"{node}: Invalid New Tags value {long_tag!r}")


def test_node_with_only_over_long_new_tags_sends_its_own_tags(channel):
    node = TopicNode(
        "topic", "Topic", tags=["own"], node_modifications={"New Tags": ["t" * 31]}
    )
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", False):
        ChannelManager(channel).validate()
    assert node.to_dict()["tags"] == ["own"]


@pytest.mark.parametrize("new_tags", [None, ""])
def test_validate_leaves_non_list_new_tags_as_given(channel, new_tags):
    node = TopicNode(
        "topic", "Topic", tags=["own"], node_modifications={"New Tags": new_tags}
    )
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", True):
        ChannelManager(channel).validate()
    assert (node.valid, node.to_dict()["tags"]) == (True, ["own"])


def test_studio_content_node_ignores_over_long_new_tags_in_strict_mode(channel):
    node = RemoteContentNode("0" * 32, source_node_id="1" * 32)
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", True):
        SushiChef().apply_modifications(
            channel, {node.source_id: {"New Tags": ["t" * 31]}}
        )
    assert "tags" not in node.to_dict()


@pytest.mark.parametrize("field, valid, invalid", CLEANABLE_VALUES)
def test_validate_raises_on_an_invalid_metadata_value_in_strict_mode(
    channel, field, valid, invalid
):
    node = TopicNode("topic", "Topic", **{field: [valid, invalid]})
    channel.add_child(node)
    with (
        patch("ricecooker.config.STRICT", True),
        pytest.raises(InvalidNodeException) as raised,
    ):
        ChannelManager(channel).validate()
    assert str(raised.value).startswith(f"{node}: Invalid {field} value {invalid!r}")


def test_process_tree_names_the_failing_node_in_strict_mode(channel):
    node = ContentNode(
        "bare-node", "Bare", license=get_license(licenses.CC_BY, copyright_holder="x")
    )
    channel.add_child(node)
    with (
        patch("ricecooker.config.STRICT", True),
        pytest.raises(InvalidNodeException) as raised,
    ):
        ChannelManager(channel).process_tree()
    assert str(raised.value) == f"{node}: No kind has been set"


def test_process_tree_reraises_a_value_error_unchanged_in_strict_mode(channel):
    node = ContentNode(
        "subtitle",
        "Subtitle",
        uri=sample_path("testsubtitles_ar.srt"),
        license=get_license(licenses.CC_BY, copyright_holder="x"),
        pipeline=FilePipeline(),
    )
    channel.add_child(node)
    with (
        patch("ricecooker.config.STRICT", True),
        pytest.raises(ValueError) as raised,
    ):
        ChannelManager(channel).process_tree()
    assert type(raised.value) is ValueError
    assert str(raised.value).startswith(
        "Missing required context for SubtitleConversionHandler"
    )


@pytest.mark.parametrize(
    "field, value",
    [(field, "not-a-list") for field in ("tags", *METADATA_LABEL_CHOICES)]
    + [("tags", ("short",))],
)
def test_validate_rejects_a_metadata_field_that_is_not_a_list(channel, field, value):
    node = TopicNode("topic", "Topic", **{field: value})
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", False):
        ChannelManager(channel).validate()
    assert node.valid is False


def test_validate_accepts_a_grade_levels_tuple(channel):
    node = TopicNode(
        "topic", "Topic", grade_levels=(levels.LOWER_SECONDARY, "not-a-label")
    )
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", False):
        ChannelManager(channel).validate()
    assert (node.valid, node.grade_levels) == (True, [levels.LOWER_SECONDARY])


def test_remote_content_node_sends_a_none_label_override_unchanged(channel):
    node = RemoteContentNode("a" * 32, source_content_id="c" * 32, grade_levels=None)
    channel.add_child(node)
    with patch("ricecooker.config.STRICT", False):
        ChannelManager(channel).validate()
    assert node.to_dict()["grade_levels"] is None


@pytest.mark.parametrize("length,warned", [(200, False), (201, True)])
def test_truncate_fields_cuts_new_title_to_max_title_length(
    channel, caplog, length, warned
):
    node = TopicNode("t", "T", node_modifications={"New Title": "x" * length})
    channel.add_child(node)
    with caplog.at_level(logging.WARNING):
        node.truncate_fields()
    assert len(node.to_dict()["title"]) == min(length, config.MAX_TITLE_LENGTH)
    assert ("title" in caplog.text and "truncating" in caplog.text) is warned


def test_truncate_fields_does_not_warn_for_remote_node_new_title(channel, caplog):
    node = RemoteContentNode("0" * 32, source_node_id="1" * 32)
    channel.add_child(node)
    node.node_modifications = {"New Title": "x" * 201}
    with caplog.at_level(logging.WARNING):
        node.truncate_fields()
    assert "truncating" not in caplog.text


@pytest.mark.parametrize("length,warnings", [(200, 0), (201, 1)])
def test_studio_content_node_title_override_is_cut_to_max_title_length(
    channel, caplog, length, warnings
):
    node = RemoteContentNode("0" * 32, source_node_id="1" * 32, title="x" * length)
    channel.add_child(node)
    with caplog.at_level(logging.WARNING):
        node.truncate_fields()
    assert len(node.to_dict()["title"]) == min(length, config.MAX_TITLE_LENGTH)
    assert caplog.text.count("truncating") == warnings


def test_studio_content_node_without_title_override_sends_no_title(channel):
    node = RemoteContentNode("0" * 32, source_node_id="1" * 32)
    channel.add_child(node)
    node.truncate_fields()
    assert "title" not in node.to_dict()


def test_truncate_fields_leaves_empty_node_modifications_alone(channel):
    node = TopicNode("t", "T")
    channel.add_child(node)
    node.truncate_fields()
    assert node.node_modifications == {}


def test_truncate_fields_leaves_non_string_new_title_alone(channel):
    node = TopicNode("t", "T", node_modifications={"New Title": 12345})
    channel.add_child(node)
    node.truncate_fields()
    assert node.node_modifications["New Title"] == 12345
