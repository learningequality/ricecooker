""" Tests for tree construction """
import os
import tempfile
import uuid
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
from le_utils.constants import content_kinds
from le_utils.constants import file_types
from le_utils.constants import format_presets
from le_utils.constants import licenses
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import levels
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type
from le_utils.constants.labels import subjects
from le_utils.constants.languages import getlang

from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.files import SlideImageFile
from ricecooker.classes.files import ThumbnailFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.licenses import License
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import CustomNavigationChannelNode
from ricecooker.classes.nodes import CustomNavigationNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import Node
from ricecooker.classes.nodes import RemoteContentNode
from ricecooker.classes.nodes import SlideshowNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import TreeNode
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
    assert (
        tree.children[0].children[0] == document
    ), "Topic should have a document child node"


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

    assert (
        channel.get_content_id() == channel_content_id
    ), "Channel content id should be {}".format(channel_content_id)
    assert (
        channel.get_node_id() == channel_node_id
    ), "Channel node id should be {}".format(channel_node_id)
    assert (
        topic.get_content_id() == topic_content_id
    ), "Topic content id should be {}".format(topic_content_id)
    assert topic.get_node_id() == topic_node_id, "Topic node id should be {}".format(
        topic_node_id
    )
    assert (
        document.get_content_id() == document_content_id
    ), "Document content id should be {}".format(document_content_id)
    assert (
        document.get_node_id() == document_node_id
    ), "Document node id should be {}".format(document_node_id)


def test_add_file(document, document_file):
    test_files = [f for f in document.files if isinstance(f, DocumentFile)]
    assert any(test_files), "Document must have at least one file"
    assert test_files[0] == document_file, "Document file was not added correctly"


def test_thumbnail(topic, document, thumbnail_path):
    assert document.has_thumbnail(), "Document must have a thumbnail"
    assert not topic.has_thumbnail(), "Topic must not have a thumbnail"
    assert [
        f for f in document.files if f.path == thumbnail_path
    ], "Document is missing a thumbnail with path {}".format(thumbnail_path)


def test_count(tree):
    assert tree.count() == 2, "Channel should have 2 descendants"


def test_get_non_topic_descendants(tree, document):
    assert tree.get_non_topic_descendants() == [
        document
    ], "Channel should only have 1 non-topic descendant"


def test_licenses(channel, topic, document, license_name, copyright_holder):
    assert isinstance(
        document.license, License
    ), "Document should have a license object"
    assert (
        document.license.license_id == license_name
    ), "Document license should have public domain license"
    assert (
        document.license.copyright_holder == copyright_holder
    ), "Document license should have copyright holder set to {}".format(
        copyright_holder
    )
    assert not channel.license, "Channel should not have a license"
    assert not topic.license, "Topic should not have a license"


def test_validate_topics(tree, invalid_tree):
    assert tree.validate(), "Valid topic should pass validation"

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
    assert parent_node.validate()
    assert parent_node
    assert parent_node.children[0]
    assert topic_node.kind == "topic"
    assert len(html5_node.files) == 3
    assert html5_node.files[2].get_preset() == format_presets.AUDIO_DEPENDENCY


""" *********** SLIDESHOW CONTENT NODE TESTS *********** """


def test_slideshow_node_via_files(channel):
    slideshow_node = SlideshowNode(
        title="The Slideshow",
        description="Slideshow Content Demo",
        source_id="demo",
        author="DE Mo",
        language="en",
        license=get_license("CC BY", copyright_holder="Demo Holdings"),
        files=[
            SlideImageFile(
                path="tests/testcontent/samples/thumbnail.jpg",
                language="en",
                caption="Demo blocks are neat.",
                descriptive_text="Demo blocks are neat.",
            ),
            SlideImageFile(
                path="tests/testcontent/samples/thumbnail.jpg",
                language="en",
                caption="Touch the demo to learn new things!",
                descriptive_text="Touch the demo to learn new things!",
            ),
            SlideImageFile(
                path="tests/testcontent/samples/thumbnail.jpg",
                language="en",
                caption="Made mostly with Python!",
                descriptive_text="Made mostly with Python!",
            ),
            SlideImageFile(
                path="tests/testcontent/samples/thumbnail.jpg",
                language="en",
                caption="Unlock your potential with this demo.",
                descriptive_text="Unlock your potential with this demo.",
            ),
            ThumbnailFile(
                path="tests/testcontent/samples/thumbnail.png", language="en"
            ),
        ],
    )
    assert slideshow_node
    assert slideshow_node.kind == "slideshow"
    assert len(slideshow_node.files) == 5, "missing files"
    assert slideshow_node.extra_fields, "missing extra_fields"
    assert "slideshow_data" in slideshow_node.extra_fields, "missing slideshow_data key"
    slideshow_node.process_files()
    channel.add_child(slideshow_node)
    assert channel.validate()
    assert slideshow_node.to_dict()  # not ready yet bcs needs ot be part of tree...


def test_slideshow_node_via_add_file(channel):
    slideshow_node = SlideshowNode(
        title="The Slideshow via add_files",
        description="Slideshow Content Demo",
        source_id="demo2",
        author="DE Mo",
        language="en",
        license=get_license("CC BY", copyright_holder="Demo Holdings"),
        files=[],
    )
    slideimg1 = SlideImageFile(
        path="tests/testcontent/samples/thumbnail.jpg",
        language="en",
        caption="Demo blocks are neat.",
        descriptive_text="Demo blocks are neat.",
    )
    slideshow_node.add_file(slideimg1)
    slideimg2 = SlideImageFile(
        path="tests/testcontent/samples/thumbnail.jpg",
        language="en",
        caption="Touch the demo to learn new things!",
        descriptive_text="Touch the demo to learn new things!",
    )
    slideshow_node.add_file(slideimg2)
    thumbimg1 = ThumbnailFile(
        path="tests/testcontent/samples/thumbnail.jpg", language="en"
    )
    slideshow_node.add_file(thumbimg1)

    # print(slideshow_node.__dict__)
    assert slideshow_node
    assert len(slideshow_node.files) == 3, "missing files"

    channel.add_child(slideshow_node)
    assert channel.validate()


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
    assert channel.validate()
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
    assert channel.validate()
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
    assert custom_navigation_channel_node.validate()
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
    assert custom_navigation_channel_node.validate()
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
    assert remote_content_node.validate()
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
    assert remote_content_node.validate()
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
    assert remote_content_node.validate()
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
    assert remote_content_node.validate()
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
    assert remote_content_node.validate()
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
            assert set(actual[field]) == set(
                value
            ), f"Metadata for {field} does not match"
        elif field == "license":
            assert (
                actual[field].license_id == value
            ), f"Metadata for {field} does not match"
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

    # Check that _error was set and validate returned True
    assert hasattr(mock_node, "_error")
    assert mock_node._error == "Test validation error"
    assert result is True


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


def test_add_nodes_handles_connection_error(channel):
    """Test that add_nodes handles ConnectionError."""
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

    # Mock the session post to raise ConnectionError
    with patch(
        "ricecooker.config.SESSION.post",
        side_effect=ConnectionError("Connection refused"),
    ):
        manager.add_nodes("root_id", parent_node)

    # Check that the error was registered in failed_node_builds
    assert "root_id" in manager.failed_node_builds
    assert manager.failed_node_builds["root_id"]["node"] == parent_node
    assert isinstance(manager.failed_node_builds["root_id"]["error"], ConnectionError)


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
    assert manager.failed_node_builds["root_id"]["content"] == b"Server error"


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

    with patch("builtins.open", mocked_open), patch(
        "ricecooker.config.get_storage_path", return_value="/tmp/test_file.mp4"
    ), patch("ricecooker.config.SESSION.post", return_value=mock_response):

        # Check that InsufficientStorageException is raised
        with pytest.raises(
            InsufficientStorageException, match="You have run out of storage space."
        ):
            manager.do_file_upload(filename)


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
