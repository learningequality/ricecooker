"""Tests for IMSCP pipeline integration (handlers + ContentNode support)."""
import os
import tempfile
import zipfile
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from helpers import create_zip_with_manifest
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


_INDEX_HTML = {"index.html": "<html><body>Content</body></html>"}


# --- Fixtures ---


@pytest.fixture
def simple_imscp_zip():
    """Create a simple IMSCP zip with manifest."""
    with create_zip_with_manifest(
        "simple_manifest.xml", extra_entries=_INDEX_HTML
    ) as path:
        yield path


@pytest.fixture
def complex_imscp_zip():
    """Create a complex IMSCP zip with external metadata."""
    with create_zip_with_manifest(
        "complete_manifest_with_external_metadata.xml",
        "metadata_hummingbirds_course.xml",
        "metadata_hummingbirds_organization.xml",
        extra_entries=_INDEX_HTML,
    ) as path:
        yield path


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
    from ricecooker.utils.imscp import parse_imscp_manifest

    extractor = IMSCPMetadataExtractor()
    manifest = parse_imscp_manifest(simple_imscp_zip)
    assert extractor._infer_preset_from_manifest(manifest) == format_presets.IMSCP_ZIP


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


def test_content_node_metadata_from_dict_logs_unknown_keys():
    """Unknown keys in dict are dropped with a debug log message."""
    from ricecooker.utils.pipeline.context import _content_node_metadata_from_dict

    with patch("ricecooker.utils.pipeline.context.logger") as mock_logger:
        result = _content_node_metadata_from_dict(
            {"title": "Test", "bogus_key": "value", "another_unknown": 42}
        )
    assert result.title == "Test"
    mock_logger.debug.assert_called_once()
    logged_keys = mock_logger.debug.call_args[0][1]
    assert "bogus_key" in logged_keys
    assert "another_unknown" in logged_keys


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
        ContentNodeMetadata(
            title="Topic 1",
            source_id="topic1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Leaf 1",
                    source_id="leaf1",
                    kind="html5",
                    extra_fields={"options": {"entry": "page1.html"}},
                ),
            ],
        ),
        ContentNodeMetadata(
            title="Leaf 2",
            source_id="leaf2",
            kind="html5",
            extra_fields={"options": {"entry": "page2.html"}},
        ),
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
        ContentNodeMetadata(
            title="Page A",
            source_id="page_a",
            kind="html5",
            extra_fields={"options": {"entry": "content/page_a.html"}},
        ),
    ]

    node._build_children_from_metadata(children_data)

    child = node.children[0]
    assert isinstance(child, ContentNode)
    assert child.extra_fields == {"options": {"entry": "content/page_a.html"}}
    assert child.kind == content_kinds.HTML5


def test_content_node_children_share_files():
    """Leaf children with file_preset get parent files; topic children do not."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        ContentNodeMetadata(
            title="Topic",
            source_id="topic1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Leaf",
                    source_id="leaf1",
                    kind="html5",
                    file_preset=format_presets.IMSCP_ZIP,
                    extra_fields={"options": {"entry": "index.html"}},
                ),
            ],
        ),
    ]

    node._build_children_from_metadata(children_data)

    topic_child = node.children[0]
    leaf_child = topic_child.children[0]
    # Topic children should not get files
    assert len(topic_child.files) == 0
    # Leaf children with file_preset get copies of parent files
    assert len(leaf_child.files) > 0


def test_content_node_children_metadata_fields_applied():
    """Metadata fields like description, tags are applied to child nodes."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        ContentNodeMetadata(
            title="Leaf",
            source_id="leaf1",
            kind="html5",
            description="A test description",
            tags=["tag1", "tag2"],
            extra_fields={"options": {"entry": "index.html"}},
        ),
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
        ContentNodeMetadata(
            title="Level 1",
            source_id="l1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Level 2",
                    source_id="l2",
                    kind="topic",
                    children=[
                        ContentNodeMetadata(
                            title="Deep Leaf",
                            source_id="deep",
                            kind="html5",
                            extra_fields={"options": {"entry": "deep.html"}},
                        ),
                    ],
                ),
            ],
        ),
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
        ContentNodeMetadata(
            title="Topic",
            source_id="topic1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Leaf",
                    source_id="leaf1",
                    kind="html5",
                    extra_fields={"options": {"entry": "index.html"}},
                ),
            ],
        ),
    ]

    node._build_children_from_metadata(children_data)

    topic_child = node.children[0]
    assert isinstance(topic_child, TopicNode)
    assert len(topic_child.files) == 0


def test_leaf_children_get_files_with_preset():
    """Leaf children with file_preset get copies of parent files with that preset."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    imscp_file = _make_mock_file(preset=format_presets.IMSCP_ZIP, filename="test.zip")
    node.add_file(imscp_file)

    children_data = [
        ContentNodeMetadata(
            title="Leaf",
            source_id="leaf1",
            kind="html5",
            file_preset=format_presets.IMSCP_ZIP,
            extra_fields={"options": {"entry": "index.html"}},
        ),
    ]

    node._build_children_from_metadata(children_data)

    child = node.children[0]
    assert len(child.files) == 1
    assert child.files[0].get_preset() == format_presets.IMSCP_ZIP
    # Child gets a copy, not the same object
    assert child.files[0] is not imscp_file


def test_children_without_file_preset_get_no_files():
    """Children without file_preset get no files."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    mock_file = _make_mock_file()
    node.add_file(mock_file)

    children_data = [
        ContentNodeMetadata(
            title="Leaf",
            source_id="leaf1",
            kind="html5",
            extra_fields={"options": {"entry": "index.html"}},
        ),
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
        ContentNodeMetadata(
            title="Topic 1",
            source_id="topic1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Leaf 1",
                    source_id="leaf1",
                    kind="html5",
                    extra_fields={"options": {"entry": "page1.html"}},
                ),
            ],
        ),
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
        ContentNodeMetadata(
            title="Level 1",
            source_id="l1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Level 2",
                    source_id="l2",
                    kind="topic",
                    children=[
                        ContentNodeMetadata(
                            title="Deep Leaf",
                            source_id="deep",
                            kind="html5",
                            extra_fields={"options": {"entry": "deep.html"}},
                        ),
                    ],
                ),
            ],
        ),
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
        ContentNodeMetadata(
            title="Topic 1",
            source_id="topic1",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Leaf 1",
                    source_id="leaf1",
                    kind="html5",
                    extra_fields={"options": {"entry": "page1.html"}},
                ),
            ],
        ),
    ]
    node._build_children_from_metadata(children_data)

    # Give the grandchild a file with a filename (simulating a processed file)
    grandchild = node.children[0].children[0]
    mock_file = _make_mock_file(filename="abc123.zip")
    grandchild.add_file(mock_file)

    # Simulate what process_files does for dynamic children:
    # The current flat loop only checks direct children, missing grandchildren
    filenames = node._validate_and_collect_dynamic_filenames(node)

    assert "abc123.zip" in filenames


def test_file_init_keys_match_file_signature():
    """Guard: _FILE_INIT_KEYS must stay in sync with File.__init__ parameters."""
    import inspect

    expected = set(inspect.signature(File.__init__).parameters) - {"self"}
    assert ContentNode._FILE_INIT_KEYS == expected, (
        f"_FILE_INIT_KEYS is out of sync with File.__init__. "
        f"Missing: {expected - ContentNode._FILE_INIT_KEYS}, "
        f"Extra: {ContentNode._FILE_INIT_KEYS - expected}"
    )


# --- QTI zip fixtures ---


@pytest.fixture
def qti_imscp_zip():
    """Create an IMSCP zip with pure QTI resources."""
    with create_zip_with_manifest(
        "qti_manifest.xml", extra_entries=_INDEX_HTML
    ) as path:
        yield path


@pytest.fixture
def mixed_imscp_zip():
    """Create an IMSCP zip with both webcontent and QTI resources."""
    with create_zip_with_manifest(
        "mixed_manifest.xml", extra_entries=_INDEX_HTML
    ) as path:
        yield path


# --- QTI metadata extraction tests (Step 3) ---


def test_metadata_extractor_sets_kind_on_content_node_metadata(simple_imscp_zip):
    """MetadataExtractor.handle_file mutates ContentNodeMetadata.kind in place.

    This characterization test guards against accidentally freezing ContentNodeMetadata.
    """
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(simple_imscp_zip)
    assert result.content_node_metadata.kind == "topic"


def test_pure_qti_metadata(qti_imscp_zip):
    """All leaves in a pure QTI package have kind=exercise and QTI_ZIP file_preset."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(qti_imscp_zip)

    metadata = result.content_node_metadata
    assert metadata.kind == "topic"
    org = metadata.children[0]

    for child in org.children:
        assert child.kind == content_kinds.EXERCISE
        assert child.file_preset == format_presets.QTI_ZIP


def test_mixed_metadata(mixed_imscp_zip):
    """Mixed package: webcontent leaves get html5/IMSCP_ZIP, QTI leaves get exercise/QTI_ZIP."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(mixed_imscp_zip)

    metadata = result.content_node_metadata
    org = metadata.children[0]

    lessons = next(c for c in org.children if c.title == "Lessons")
    quizzes = next(c for c in org.children if c.title == "Quizzes")

    # Webcontent leaf
    lesson1 = lessons.children[0]
    assert lesson1.kind == content_kinds.HTML5
    assert lesson1.file_preset == format_presets.IMSCP_ZIP

    # QTI leaves
    for quiz in quizzes.children:
        assert quiz.kind == content_kinds.EXERCISE
        assert quiz.file_preset == format_presets.QTI_ZIP


def test_pure_imscp_metadata_unchanged(simple_imscp_zip):
    """Regression: pure webcontent packages still produce html5/IMSCP_ZIP leaves."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(simple_imscp_zip)

    metadata = result.content_node_metadata
    org = metadata.children[0]

    # All leaves should be html5/IMSCP_ZIP
    def check_leaves(node):
        if node.children:
            for child in node.children:
                check_leaves(child)
        else:
            assert node.kind == content_kinds.HTML5
            assert node.file_preset == format_presets.IMSCP_ZIP

    check_leaves(org)


def test_qti_entry_point(qti_imscp_zip):
    """QTI leaf nodes have extra_fields.options.entry pointing to QTI XML."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(qti_imscp_zip)

    org = result.content_node_metadata.children[0]
    q1 = org.children[0]
    assert q1.extra_fields["options"]["entry"] == "question1.xml"
    q2 = org.children[1]
    assert q2.extra_fields["options"]["entry"] == "question2.xml"


def test_mixed_package_single_file_preset(mixed_imscp_zip):
    """Mixed package still produces a single FileMetadata with IMSCP_ZIP preset."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(mixed_imscp_zip)

    # One preset per file — children override preset via copy
    assert result.preset == format_presets.IMSCP_ZIP


def test_pure_qti_single_file_registration(qti_imscp_zip):
    """Pure QTI package produces a single file with QTI_ZIP preset."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(qti_imscp_zip)

    assert result.preset == format_presets.QTI_ZIP


def test_pure_imscp_single_file_preset(simple_imscp_zip):
    """Pure IMSCP package produces a single file with IMSCP_ZIP preset."""
    extractor = IMSCPMetadataExtractor()
    result = extractor.handle_file(simple_imscp_zip)

    assert result.preset == format_presets.IMSCP_ZIP


def test_handle_file_opens_zip_at_most_twice(mixed_imscp_zip):
    """handle_file should not redundantly open the zip file."""
    open_count = 0
    original_init = zipfile.ZipFile.__init__

    def counting_init(self, *args, **kwargs):
        nonlocal open_count
        open_count += 1
        return original_init(self, *args, **kwargs)

    extractor = IMSCPMetadataExtractor()
    with patch.object(zipfile.ZipFile, "__init__", counting_init):
        extractor.handle_file(mixed_imscp_zip)

    assert open_count <= 2, f"Zip opened {open_count} times, expected at most 2"


# --- Node building tests for QTI (Step 5) ---


def test_qti_leaf_nodes_are_exercise_kind():
    """Dynamically created leaf nodes from QTI metadata have kind='exercise'."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    imscp_file = _make_mock_file(preset=format_presets.QTI_ZIP, filename="test.zip")
    node.add_file(imscp_file)

    children_data = [
        ContentNodeMetadata(
            title="Question 1",
            source_id="q1",
            kind=content_kinds.EXERCISE,
            file_preset=format_presets.QTI_ZIP,
            extra_fields={"options": {"entry": "question1.xml"}},
        ),
        ContentNodeMetadata(
            title="Question 2",
            source_id="q2",
            kind=content_kinds.EXERCISE,
            file_preset=format_presets.QTI_ZIP,
            extra_fields={"options": {"entry": "question2.xml"}},
        ),
    ]

    node._build_children_from_metadata(children_data)

    for child in node.children:
        assert isinstance(child, ContentNode)
        assert child.kind == content_kinds.EXERCISE
        assert len(child.files) == 1
        assert child.files[0].get_preset() == format_presets.QTI_ZIP


def test_mixed_tree_structure():
    """Mixed tree: one parent file, children get copies with correct preset."""
    license = _make_license()
    node = ContentNode("root_id", "Root", license)
    # Only ONE file — children copy it with the right preset
    imscp_file = _make_mock_file(preset=format_presets.IMSCP_ZIP, filename="test.zip")
    node.add_file(imscp_file)

    children_data = [
        ContentNodeMetadata(
            title="Lessons",
            source_id="lessons",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Lesson 1",
                    source_id="l1",
                    kind=content_kinds.HTML5,
                    file_preset=format_presets.IMSCP_ZIP,
                    extra_fields={"options": {"entry": "lesson1.html"}},
                ),
            ],
        ),
        ContentNodeMetadata(
            title="Quizzes",
            source_id="quizzes",
            kind="topic",
            children=[
                ContentNodeMetadata(
                    title="Quiz 1",
                    source_id="quiz1",
                    kind=content_kinds.EXERCISE,
                    file_preset=format_presets.QTI_ZIP,
                    extra_fields={"options": {"entry": "quiz1.xml"}},
                ),
            ],
        ),
    ]

    node._build_children_from_metadata(children_data)

    lessons = node.children[0]
    quizzes = node.children[1]

    lesson1 = lessons.children[0]
    assert lesson1.kind == content_kinds.HTML5
    assert lesson1.files[0].get_preset() == format_presets.IMSCP_ZIP

    quiz1 = quizzes.children[0]
    assert quiz1.kind == content_kinds.EXERCISE
    assert quiz1.files[0].get_preset() == format_presets.QTI_ZIP


def test_exercise_kind_in_activity_map():
    """Exercise kind maps to PRACTICE learning activity."""
    from ricecooker.classes.nodes import kind_activity_map
    from le_utils.constants.labels import learning_activities

    assert content_kinds.EXERCISE in kind_activity_map
    assert kind_activity_map[content_kinds.EXERCISE] == learning_activities.PRACTICE


def test_process_uri_logs_dropped_keys():
    """_process_uri logs debug message when FileMetadata keys are filtered out."""
    license = _make_license()

    root_meta = ContentNodeMetadata(title="Leaf Content", kind="html5")
    file_metadata = FileMetadata(
        preset=format_presets.IMSCP_ZIP,
        license="CC BY",
        license_description="Creative Commons Attribution",
        content_node_metadata=root_meta,
        path="test.zip",
    )

    mock_pipeline = MagicMock()
    mock_pipeline.should_handle.return_value = True
    mock_pipeline.execute.return_value = [file_metadata]

    node = ContentNode(
        "root_id", "Root", license, uri="test.zip", pipeline=mock_pipeline
    )

    with patch("ricecooker.classes.nodes.config") as mock_config:
        mock_config.UPDATE = False
        mock_logger = MagicMock()
        mock_config.LOGGER = mock_logger
        node._process_uri()

    mock_logger.debug.assert_called()
    # The log message should mention the dropped keys
    assert "license" in str(mock_logger.debug.call_args)
    # Title from pipeline metadata should have been applied
    assert node.title == "Leaf Content"


def test_process_uri_handles_license_in_file_metadata():
    """_process_uri doesn't crash when FileMetadata has license fields set."""
    license = _make_license()

    root_meta = ContentNodeMetadata(title="Leaf Content", kind="html5")
    file_metadata = FileMetadata(
        preset=format_presets.IMSCP_ZIP,
        license="CC BY",
        license_description="Creative Commons Attribution",
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

    assert len(node.files) == 1
    assert node.files[0].get_preset() == format_presets.IMSCP_ZIP


def test_process_uri_applies_language_from_metadata():
    """Pipeline metadata language should be applied to the node."""
    license = _make_license()

    root_meta = ContentNodeMetadata(title="Leaf Content", kind="html5", language="fr")
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

    assert node.language == "fr"


def test_process_uri_does_not_overwrite_source_id():
    """Pipeline metadata source_id must not overwrite the node's constructor value."""
    license = _make_license()

    root_meta = ContentNodeMetadata(
        title="New Title", kind="html5", source_id="pipeline_source_id"
    )
    file_metadata = FileMetadata(
        preset=format_presets.IMSCP_ZIP,
        content_node_metadata=root_meta,
        path="test.zip",
    )

    mock_pipeline = MagicMock()
    mock_pipeline.should_handle.return_value = True
    mock_pipeline.execute.return_value = [file_metadata]

    node = ContentNode(
        "original_source_id", "Root", license, uri="test.zip", pipeline=mock_pipeline
    )
    node._process_uri()

    assert node.source_id == "original_source_id"


def test_process_uri_does_not_overwrite_license():
    """Pipeline metadata license must not overwrite the node's constructor value."""
    license = _make_license()

    root_meta = ContentNodeMetadata(title="New Title", kind="html5", license="CC BY-SA")
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

    assert node.license == license


def test_metadata_apply_fields_is_class_constant():
    """_METADATA_APPLY_FIELDS should be accessible as a class-level constant."""
    assert hasattr(ContentNode, "_METADATA_APPLY_FIELDS")
    assert isinstance(ContentNode._METADATA_APPLY_FIELDS, tuple)


def test_process_uri_does_not_apply_copyright_holder():
    """Pipeline metadata copyright_holder must not be applied to the node.

    copyright_holder is an identity/legal field like source_id and license,
    so it is intentionally excluded from _METADATA_APPLY_FIELDS.
    """
    license = _make_license()

    root_meta = ContentNodeMetadata(
        title="New Title", kind="html5", copyright_holder="Pipeline Holder"
    )
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

    # copyright_holder is not in _METADATA_APPLY_FIELDS, so it should
    # never be set as a direct attribute on the node
    assert not hasattr(node, "copyright_holder")
    # The license object retains its original copyright_holder
    assert node.license.copyright_holder == "Test Author"


def test_process_uri_children_get_correct_preset_via_copy():
    """_process_uri with mixed metadata: children get file copies with correct presets."""
    license = _make_license()

    child_meta = ContentNodeMetadata(
        title="Lesson 1",
        kind=content_kinds.HTML5,
        source_id="l1",
        file_preset=format_presets.IMSCP_ZIP,
        extra_fields={"options": {"entry": "lesson1.html"}},
    )
    quiz_meta = ContentNodeMetadata(
        title="Quiz 1",
        kind=content_kinds.EXERCISE,
        source_id="q1",
        file_preset=format_presets.QTI_ZIP,
        extra_fields={"options": {"entry": "quiz1.xml"}},
    )
    root_meta = ContentNodeMetadata(
        title="Mixed", kind="topic", children=[child_meta, quiz_meta]
    )
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

    # Parent has single file
    assert len(node.files) == 1
    assert node.files[0].get_preset() == format_presets.IMSCP_ZIP

    # Children get copies with the right presets
    lesson = node.children[0]
    quiz = node.children[1]
    assert lesson.files[0].get_preset() == format_presets.IMSCP_ZIP
    assert quiz.files[0].get_preset() == format_presets.QTI_ZIP
