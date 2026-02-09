"""Tests for IMSCP pipeline integration (handlers + ContentNode support)."""
import os
import tempfile
import zipfile
from unittest.mock import MagicMock

import pytest
from le_utils.constants import content_kinds
from le_utils.constants import format_presets
from le_utils.constants import licenses

from ricecooker.classes.files import File
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.utils.pipeline.context import ContentNodeMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.convert import IMSCPConversionHandler
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.extract_metadata import IMSCPMetadataExtractor


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
IMS_XML_DIR = os.path.join(BASE_PATH, "testcontent", "samples", "ims_xml")


# --- Fixtures ---


@pytest.fixture
def simple_imscp_zip():
    """Create a simple IMSCP zip with manifest."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    manifest_file = os.path.join(IMS_XML_DIR, "simple_manifest.xml")
    with zipfile.ZipFile(temp_zip_path, "w") as zf:
        zf.write(manifest_file, "imsmanifest.xml")
        # Add index.html so it also qualifies as HTML5 if needed
        zf.writestr("index.html", "<html><body>IMSCP Content</body></html>")
    yield temp_zip_path
    try:
        os.remove(temp_zip_path)
    except (FileNotFoundError, OSError):
        pass


@pytest.fixture
def complex_imscp_zip():
    """Create a complex IMSCP zip with external metadata."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    with zipfile.ZipFile(temp_zip_path, "w") as zf:
        zf.write(
            os.path.join(IMS_XML_DIR, "complete_manifest_with_external_metadata.xml"),
            "imsmanifest.xml",
        )
        zf.write(
            os.path.join(IMS_XML_DIR, "metadata_hummingbirds_course.xml"),
            "metadata_hummingbirds_course.xml",
        )
        zf.write(
            os.path.join(IMS_XML_DIR, "metadata_hummingbirds_organization.xml"),
            "metadata_hummingbirds_organization.xml",
        )
        zf.writestr("index.html", "<html><body>Hummingbirds</body></html>")
    yield temp_zip_path
    try:
        os.remove(temp_zip_path)
    except (FileNotFoundError, OSError):
        pass


@pytest.fixture
def regular_html5_zip():
    """Create a regular HTML5 zip without manifest."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    with zipfile.ZipFile(temp_zip_path, "w") as zf:
        zf.writestr("index.html", "<html><body>Regular HTML5</body></html>")
    yield temp_zip_path
    try:
        os.remove(temp_zip_path)
    except (FileNotFoundError, OSError):
        pass


# --- ConversionHandler tests ---


def test_imscp_conversion_handler_should_handle_imscp_zip(simple_imscp_zip):
    handler = IMSCPConversionHandler()
    assert handler.should_handle(simple_imscp_zip) is True


def test_imscp_conversion_handler_should_not_handle_regular_html5(regular_html5_zip):
    handler = IMSCPConversionHandler()
    assert handler.should_handle(regular_html5_zip) is False


def test_imscp_conversion_handler_validates_manifest_exists(simple_imscp_zip):
    """Validation passes when imsmanifest.xml is present and parseable."""
    handler = IMSCPConversionHandler()
    # Should not raise
    handler.validate_archive(simple_imscp_zip)


def test_imscp_conversion_handler_validates_invalid_manifest():
    """Validation fails for zip without imsmanifest.xml."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("index.html", "<html><body>No manifest</body></html>")
        handler = IMSCPConversionHandler()
        with pytest.raises(InvalidFileException):
            handler.validate_archive(temp_zip_path)
    finally:
        os.remove(temp_zip_path)


# --- MetadataExtractor tests ---


def test_imscp_metadata_extractor_should_handle(simple_imscp_zip):
    extractor = IMSCPMetadataExtractor()
    assert extractor.should_handle(simple_imscp_zip) is True


def test_imscp_metadata_extractor_should_not_handle_regular_html5(regular_html5_zip):
    extractor = IMSCPMetadataExtractor()
    assert extractor.should_handle(regular_html5_zip) is False


def test_imscp_metadata_extractor_preset(simple_imscp_zip):
    extractor = IMSCPMetadataExtractor()
    assert extractor.infer_preset(simple_imscp_zip) == format_presets.IMSCP_ZIP


def test_imscp_metadata_extractor_simple_manifest(simple_imscp_zip):
    """Simple manifest produces nested ContentNodeMetadata with children."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(simple_imscp_zip)

    assert isinstance(result, FileMetadata)
    assert result.preset == format_presets.IMSCP_ZIP

    metadata = result.content_node_metadata
    assert isinstance(metadata, ContentNodeMetadata)
    assert metadata.title == "Test File"
    assert metadata.kind == "topic"
    assert metadata.children is not None
    assert len(metadata.children) == 2  # 2 organizations


def test_imscp_metadata_extractor_complex_manifest(complex_imscp_zip):
    """Complex manifest with external metadata produces rich nested metadata."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(complex_imscp_zip)

    metadata = result.content_node_metadata
    assert metadata.title == "Discovering Hummingbirds"
    assert metadata.kind == "topic"
    assert metadata.children is not None
    assert len(metadata.children) == 1  # 1 organization

    org = metadata.children[0]
    assert isinstance(org, ContentNodeMetadata)
    assert org.title == "Discovering Hummingbirds"
    assert org.children is not None
    assert len(org.children) == 3


def test_imscp_metadata_extractor_leaf_entry_points(complex_imscp_zip):
    """Leaf nodes have extra_fields.options.entry set."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(complex_imscp_zip)

    org = result.content_node_metadata.children[0]
    leaf = org.children[0]  # "Introduction to Hummingbirds"
    assert leaf.kind == "html5"
    assert leaf.extra_fields is not None
    assert leaf.extra_fields["options"]["entry"] == "intro.html"


def test_imscp_metadata_extractor_scorm_metadata_applied(complex_imscp_zip):
    """SCORM educational metadata is mapped to learning_activities etc."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(complex_imscp_zip)

    metadata = result.content_node_metadata
    # The complex manifest has keyword metadata
    assert metadata.tags is not None
    assert "hummingbirds" in metadata.tags


# --- ContentNodeMetadata children field tests ---


def test_content_node_metadata_children_field_defaults_none():
    metadata = ContentNodeMetadata()
    assert metadata.children is None


def test_content_node_metadata_with_children_serializes():
    """FileMetadata.to_dict() recursively serializes nested children."""
    child = ContentNodeMetadata(title="Child", kind="html5")
    parent = ContentNodeMetadata(title="Parent", kind="topic", children=[child])
    fm = FileMetadata(content_node_metadata=parent)
    result = fm.to_dict()

    assert "content_node_metadata" in result
    assert result["content_node_metadata"]["title"] == "Parent"
    assert len(result["content_node_metadata"]["children"]) == 1
    assert result["content_node_metadata"]["children"][0]["title"] == "Child"


def test_file_metadata_merge_with_children():
    """Merge preserves children structure."""
    child = ContentNodeMetadata(title="Child", kind="html5")
    parent = ContentNodeMetadata(title="Parent", kind="topic", children=[child])
    fm1 = FileMetadata(content_node_metadata=parent)
    fm2 = FileMetadata(preset="some_preset")

    merged = fm1.merge(fm2)
    assert merged.preset == "some_preset"
    # children should be preserved through merge
    merged_dict = merged.to_dict()
    assert len(merged_dict["content_node_metadata"]["children"]) == 1


# --- ContentNode nested children support tests (Step 5) ---


def _make_license():
    """Create a license object for testing."""
    from ricecooker.classes.licenses import get_license

    return get_license(licenses.CC_BY, copyright_holder="Test Author")


def _make_mock_file(preset=format_presets.IMSCP_ZIP, filename="test.zip"):
    """Create a mock File object for testing."""
    f = File(preset=preset)
    f.filename = filename
    return f


def test_content_node_builds_children_from_nested_metadata():
    """_build_children_from_metadata creates TopicNode/ContentNode children."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Topic 1",
            "source_id": "topic1",
            "kind": "topic",
            "children": [
                {
                    "title": "Leaf 1",
                    "source_id": "leaf1",
                    "kind": "html5",
                    "extra_fields": {"options": {"entry": "page1.html"}},
                },
            ],
        },
        {
            "title": "Leaf 2",
            "source_id": "leaf2",
            "kind": "html5",
            "extra_fields": {"options": {"entry": "page2.html"}},
        },
    ]

    node._build_children_from_metadata(children_data)

    assert len(node.children) == 2
    assert isinstance(node.children[0], TopicNode)
    assert node.children[0].title == "Topic 1"
    assert node.children[0].source_id == "topic1"
    assert isinstance(node.children[1], ContentNode)
    assert node.children[1].title == "Leaf 2"
    assert node.children[1].source_id == "leaf2"


def test_content_node_becomes_topic_when_has_children():
    """When pipeline returns nested metadata, root ContentNode gets kind=topic."""
    license = _make_license()

    # Build a ContentNodeMetadata with children
    child_meta = ContentNodeMetadata(
        title="Leaf",
        kind="html5",
        source_id="leaf1",
        extra_fields={"options": {"entry": "index.html"}},
    )
    root_meta = ContentNodeMetadata(
        title="Root Topic", kind="topic", children=[child_meta]
    )
    file_metadata = FileMetadata(
        preset=format_presets.IMSCP_ZIP,
        content_node_metadata=root_meta,
        path="test.zip",
    )

    # Mock pipeline to return our metadata
    mock_pipeline = MagicMock()
    mock_pipeline.should_handle.return_value = True
    mock_pipeline.execute.return_value = [file_metadata]

    node = ContentNode(
        "root_id", "Root", license, uri="test.zip", pipeline=mock_pipeline
    )
    node._process_uri()

    assert node.kind == "topic"
    assert node.title == "Root Topic"


def test_content_node_children_have_entry_points():
    """Leaf children have correct extra_fields.options.entry."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Page A",
            "source_id": "page_a",
            "kind": "html5",
            "extra_fields": {"options": {"entry": "content/page_a.html"}},
        },
    ]

    node._build_children_from_metadata(children_data)

    child = node.children[0]
    assert isinstance(child, ContentNode)
    assert child.extra_fields == {"options": {"entry": "content/page_a.html"}}
    assert child.kind == content_kinds.HTML5


def test_content_node_children_share_files():
    """Leaf children with file_presets get parent files; topic children do not."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Topic",
            "source_id": "topic1",
            "kind": "topic",
            "children": [
                {
                    "title": "Leaf",
                    "source_id": "leaf1",
                    "kind": "html5",
                    "file_presets": [format_presets.IMSCP_ZIP],
                    "extra_fields": {"options": {"entry": "index.html"}},
                },
            ],
        },
    ]

    node._build_children_from_metadata(children_data)

    topic_child = node.children[0]
    leaf_child = topic_child.children[0]
    # Topic children should not get files
    assert len(topic_child.files) == 0
    # Leaf children with matching file_presets should get files
    assert len(leaf_child.files) > 0


def test_content_node_children_metadata_fields_applied():
    """Metadata fields like description, tags are applied to child nodes."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Leaf",
            "source_id": "leaf1",
            "kind": "html5",
            "description": "A test description",
            "tags": ["tag1", "tag2"],
            "extra_fields": {"options": {"entry": "index.html"}},
        },
    ]

    node._build_children_from_metadata(children_data)

    child = node.children[0]
    assert child.description == "A test description"
    assert "tag1" in child.tags
    assert "tag2" in child.tags


def test_content_node_dynamic_children_flag():
    """_process_uri sets _dynamic_children flag when children data exists."""
    license = _make_license()

    child_meta = ContentNodeMetadata(
        title="Leaf",
        kind="html5",
        source_id="leaf1",
        extra_fields={"options": {"entry": "index.html"}},
    )
    root_meta = ContentNodeMetadata(title="Root", kind="topic", children=[child_meta])
    file_metadata = FileMetadata(
        preset=format_presets.IMSCP_ZIP,
        content_node_metadata=root_meta,
        path="test.zip",
    )

    mock_pipeline = MagicMock()
    mock_pipeline.should_handle.return_value = True
    mock_pipeline.execute.return_value = [file_metadata]

    node = ContentNode(
        "root_id", "Root", license, uri="test.zip", pipeline=mock_pipeline
    )
    node._process_uri()

    assert node._dynamic_children is True
    assert len(node.children) == 1


def test_content_node_no_children_no_dynamic_flag():
    """_process_uri does not set _dynamic_children when no children data."""
    license = _make_license()

    root_meta = ContentNodeMetadata(title="Leaf Content", kind="html5")
    file_metadata = FileMetadata(
        preset=format_presets.IMSCP_ZIP,
        content_node_metadata=root_meta,
        path="test.zip",
    )

    mock_pipeline = MagicMock()
    mock_pipeline.should_handle.return_value = True
    mock_pipeline.execute.return_value = [file_metadata]

    node = ContentNode(
        "root_id", "Root", license, uri="test.zip", pipeline=mock_pipeline
    )
    node._process_uri()

    assert not getattr(node, "_dynamic_children", False)


def test_content_node_recursive_children_structure():
    """_build_children_from_metadata handles deeply nested structures."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Level 1",
            "source_id": "l1",
            "kind": "topic",
            "children": [
                {
                    "title": "Level 2",
                    "source_id": "l2",
                    "kind": "topic",
                    "children": [
                        {
                            "title": "Deep Leaf",
                            "source_id": "deep",
                            "kind": "html5",
                            "extra_fields": {"options": {"entry": "deep.html"}},
                        },
                    ],
                },
            ],
        },
    ]

    node._build_children_from_metadata(children_data)

    l1 = node.children[0]
    assert isinstance(l1, TopicNode)
    assert l1.title == "Level 1"

    l2 = l1.children[0]
    assert isinstance(l2, TopicNode)
    assert l2.title == "Level 2"

    deep = l2.children[0]
    assert isinstance(deep, ContentNode)
    assert deep.title == "Deep Leaf"
    assert deep.extra_fields["options"]["entry"] == "deep.html"


def test_topic_children_have_no_files():
    """TopicNode children should not inherit parent files."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Topic",
            "source_id": "topic1",
            "kind": "topic",
            "children": [
                {
                    "title": "Leaf",
                    "source_id": "leaf1",
                    "kind": "html5",
                    "extra_fields": {"options": {"entry": "index.html"}},
                },
            ],
        },
    ]

    node._build_children_from_metadata(children_data)

    topic_child = node.children[0]
    assert isinstance(topic_child, TopicNode)
    assert len(topic_child.files) == 0


def test_leaf_children_get_files_by_preset():
    """Leaf children with file_presets get only files matching their presets."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    imscp_file = _make_mock_file(preset=format_presets.IMSCP_ZIP, filename="test.zip")
    node.add_file(imscp_file)

    children_data = [
        {
            "title": "Leaf",
            "source_id": "leaf1",
            "kind": "html5",
            "file_presets": [format_presets.IMSCP_ZIP],
            "extra_fields": {"options": {"entry": "index.html"}},
        },
    ]

    node._build_children_from_metadata(children_data)

    child = node.children[0]
    assert len(child.files) == 1
    assert child.files[0].get_preset() == format_presets.IMSCP_ZIP


def test_children_without_file_presets_get_no_files():
    """Children without file_presets get no files."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Leaf",
            "source_id": "leaf1",
            "kind": "html5",
            "extra_fields": {"options": {"entry": "index.html"}},
        },
    ]

    node._build_children_from_metadata(children_data)

    child = node.children[0]
    assert len(child.files) == 0


# --- License propagation tests (Issue 1) ---


def test_license_propagated_to_nested_content_nodes():
    """Leaf ContentNodes inside TopicNodes inherit the parent's license."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Topic 1",
            "source_id": "topic1",
            "kind": "topic",
            "children": [
                {
                    "title": "Leaf 1",
                    "source_id": "leaf1",
                    "kind": "html5",
                    "extra_fields": {"options": {"entry": "page1.html"}},
                },
            ],
        },
    ]

    node._build_children_from_metadata(children_data)

    topic = node.children[0]
    leaf = topic.children[0]
    assert isinstance(leaf, ContentNode)
    assert leaf.license == license


def test_license_propagated_through_deep_nesting():
    """License propagates through Topic->Topic->Leaf (3 levels)."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        {
            "title": "Level 1",
            "source_id": "l1",
            "kind": "topic",
            "children": [
                {
                    "title": "Level 2",
                    "source_id": "l2",
                    "kind": "topic",
                    "children": [
                        {
                            "title": "Deep Leaf",
                            "source_id": "deep",
                            "kind": "html5",
                            "extra_fields": {"options": {"entry": "deep.html"}},
                        },
                    ],
                },
            ],
        },
    ]

    node._build_children_from_metadata(children_data)

    l1 = node.children[0]
    l2 = l1.children[0]
    deep = l2.children[0]
    assert isinstance(deep, ContentNode)
    assert deep.license == license


# --- process_files recursive collection tests (Issue 2) ---


def test_process_files_collects_grandchild_filenames():
    """process_files collects filenames from grandchildren inside TopicNodes."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    node.kind = content_kinds.TOPIC
    node._dynamic_children = True

    # Build Topic -> Leaf structure
    children_data = [
        {
            "title": "Topic 1",
            "source_id": "topic1",
            "kind": "topic",
            "children": [
                {
                    "title": "Leaf 1",
                    "source_id": "leaf1",
                    "kind": "html5",
                    "extra_fields": {"options": {"entry": "page1.html"}},
                },
            ],
        },
    ]
    node._build_children_from_metadata(children_data)

    # Give the grandchild a file with a filename (simulating a processed file)
    grandchild = node.children[0].children[0]
    mock_file = _make_mock_file(filename="abc123.zip")
    grandchild.add_file(mock_file)

    # Simulate what process_files does for dynamic children:
    # The current flat loop only checks direct children, missing grandchildren
    filenames = node._collect_dynamic_filenames(node)

    assert "abc123.zip" in filenames
