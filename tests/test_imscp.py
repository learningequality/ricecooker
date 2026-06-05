"""Tests for IMSCP manifest parsing (ricecooker.utils.imscp)."""
import os
import tempfile
import zipfile

import pytest
from helpers import create_zip_with_manifest

from ricecooker.utils.imscp import _SAFE_PARSER
from ricecooker.utils.imscp import flatten_single_child_topics
from ricecooker.utils.imscp import has_imscp_manifest
from ricecooker.utils.imscp import has_qti_items
from ricecooker.utils.imscp import has_qti_resources
from ricecooker.utils.imscp import has_webcontent_items
from ricecooker.utils.imscp import is_qti_resource
from ricecooker.utils.imscp import ManifestParseError
from ricecooker.utils.imscp import parse_imscp_manifest
from ricecooker.utils.SCORM_metadata import metadata_dict_to_content_node_fields


# --- Safe parser tests ---


def test_safe_parser_disables_entity_resolution():
    """_SAFE_PARSER does not resolve XML entities."""
    from lxml import etree
    import io

    # XML with an internal entity reference
    xml_bytes = b"""<?xml version="1.0"?>
    <!DOCTYPE foo [<!ENTITY xxe "expanded">]>
    <root>&xxe;</root>"""
    tree = etree.parse(io.BytesIO(xml_bytes), _SAFE_PARSER)
    # With resolve_entities=False the entity reference is NOT resolved into text
    assert tree.getroot().text is None


# --- Null guard / error handling tests ---


def test_parse_manifest_without_resources_element():
    """Manifest with <organizations> but no <resources> should not crash."""
    manifest_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<manifest>
    <metadata><lom><general><title><string>No Resources</string></title></general></lom></metadata>
    <organizations>
        <organization>
            <title>Org</title>
            <item identifier="i1" identifierref="r1"><title>Item 1</title></item>
        </organization>
    </organizations>
</manifest>"""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("imsmanifest.xml", manifest_content)
        result = parse_imscp_manifest(temp_zip_path)
        # Should not crash; the item with identifierref won't resolve
        assert result["metadata"]["title"] == "No Resources"
        assert len(result["organizations"]) == 1
    finally:
        os.remove(temp_zip_path)


def test_resolve_metadata_with_missing_external_file():
    """<adlcp:location> pointing to nonexistent file in zip raises ManifestParseError."""
    manifest_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<manifest xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_v1p3">
    <metadata>
        <adlcp:location>nonexistent_metadata.xml</adlcp:location>
    </metadata>
    <organizations>
        <organization>
            <title>Test</title>
        </organization>
    </organizations>
    <resources/>
</manifest>"""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("imsmanifest.xml", manifest_content)
        with pytest.raises(ManifestParseError, match="nonexistent_metadata.xml"):
            parse_imscp_manifest(temp_zip_path)
    finally:
        os.remove(temp_zip_path)


# --- Manifest parsing tests ---


def test_parse_simple_manifest():
    """Simple IMSCP zip produces correct identifier, metadata, organizations."""
    with create_zip_with_manifest("simple_manifest.xml") as zip_path:
        result = parse_imscp_manifest(zip_path)

    assert result["identifier"] is None  # simple_manifest.xml has no identifier attr
    assert result["metadata"]["title"] == "Test File"
    assert result["metadata"]["description"] == "Example of test file"
    assert result["metadata"]["language"] == "en"

    # Should have 2 organizations
    assert len(result["organizations"]) == 2

    # First organization: "Folder 1" with children
    org1 = result["organizations"][0]
    assert org1["title"] == "Folder 1"
    assert "children" in org1

    # Check leaf items have href and files from resource linking
    leaves = [c for c in org1["children"] if "children" not in c]
    assert len(leaves) >= 2
    assert leaves[0]["title"] == "Test File1"
    assert leaves[0]["href"] == "file1.html"


def test_parse_complex_manifest_with_external_metadata():
    """Complex manifest with external metadata references resolves metadata properly."""
    with create_zip_with_manifest(
        "complete_manifest_with_external_metadata.xml",
        "metadata_hummingbirds_course.xml",
        "metadata_hummingbirds_organization.xml",
    ) as zip_path:
        result = parse_imscp_manifest(zip_path)

    assert (
        result["identifier"]
        == "com.example.hummingbirds.contentpackaging.metadata.2024"
    )
    assert result["metadata"]["title"] == "Discovering Hummingbirds"
    assert "hummingbirds" in result["metadata"]["keyword"]
    assert result["metadata"]["language"] == "en"

    # Should have 1 organization with 3 items
    assert len(result["organizations"]) == 1
    org = result["organizations"][0]
    assert org["title"] == "Discovering Hummingbirds"
    assert len(org["children"]) == 3

    # Check items have resources linked
    item1 = org["children"][0]
    assert item1["title"] == "Introduction to Hummingbirds"
    assert item1["href"] == "intro.html"
    assert "intro.html" in item1["files"]


def test_parse_manifest_language_detection():
    """Language codes like en-US in metadata are detected."""
    with create_zip_with_manifest(
        "complete_manifest_with_external_metadata.xml",
        "metadata_hummingbirds_course.xml",
        "metadata_hummingbirds_organization.xml",
    ) as zip_path:
        result = parse_imscp_manifest(zip_path)

    # Item 1 has language "en-US" in its metadata
    org = result["organizations"][0]
    item1 = org["children"][0]
    assert item1["metadata"].get("language") == "en-US"


def test_parse_manifest_with_explicit_language():
    """Passing language parameter uses it for preferred denesting."""
    with create_zip_with_manifest("simple_manifest.xml") as zip_path:
        result = parse_imscp_manifest(zip_path, language="en")

    assert result["metadata"]["title"] == "Test File"


# --- Flattening tests ---


def test_flatten_single_child_organizations():
    """Single-child topic chains are collapsed."""
    item = {
        "title": "Outer",
        "metadata": {},
        "children": [
            {
                "title": "Inner",
                "metadata": {"description": "inner desc"},
                "children": [
                    {"title": "Leaf1", "metadata": {}, "href": "page1.html"},
                    {"title": "Leaf2", "metadata": {}, "href": "page2.html"},
                ],
            }
        ],
    }
    result = flatten_single_child_topics(item)

    # Outer should be collapsed into Inner
    assert result["title"] == "Inner"
    assert len(result["children"]) == 2
    assert result["children"][0]["title"] == "Leaf1"


def test_flatten_preserves_multi_child():
    """Multi-child structures are not flattened."""
    item = {
        "title": "Parent",
        "metadata": {},
        "children": [
            {"title": "Child1", "metadata": {}, "href": "page1.html"},
            {"title": "Child2", "metadata": {}, "href": "page2.html"},
        ],
    }
    result = flatten_single_child_topics(item)

    assert result["title"] == "Parent"
    assert len(result["children"]) == 2


def test_flatten_deep_single_chain():
    """Deep single-child chains are fully collapsed."""
    item = {
        "title": "L1",
        "metadata": {},
        "children": [
            {
                "title": "L2",
                "metadata": {},
                "children": [
                    {
                        "title": "L3",
                        "metadata": {},
                        "children": [
                            {"title": "Leaf", "metadata": {}, "href": "page.html"},
                        ],
                    }
                ],
            }
        ],
    }
    result = flatten_single_child_topics(item)

    # L1 -> L2 -> L3 (single child that is a leaf, not a topic) should stop at L3
    # L3 has one child that is a leaf (no children key), so L3 stays
    # L2 has one child (L3) that is a topic, so L2 collapses to L3
    # L1 has one child (L2->L3) that is a topic, so L1 collapses to L3
    assert result["title"] == "L3"
    assert len(result["children"]) == 1
    assert result["children"][0]["title"] == "Leaf"


def test_flatten_preserves_parent_title_when_child_has_none():
    """When child has no title, parent's title is preserved."""
    item = {
        "title": "Parent Title",
        "metadata": {},
        "children": [
            {
                "metadata": {"description": "child desc"},
                "children": [
                    {"title": "Leaf1", "metadata": {}, "href": "page1.html"},
                    {"title": "Leaf2", "metadata": {}, "href": "page2.html"},
                ],
            }
        ],
    }
    result = flatten_single_child_topics(item)

    # Child has no title, so parent's title should be used
    assert result["title"] == "Parent Title"
    assert len(result["children"]) == 2


def test_flatten_replaces_empty_string_title_with_parent():
    """When child has an empty-string title, parent's title is used."""
    item = {
        "title": "Parent Title",
        "metadata": {},
        "children": [
            {
                "title": "",
                "metadata": {},
                "children": [
                    {"title": "Leaf", "metadata": {}, "href": "page.html"},
                ],
            }
        ],
    }
    result = flatten_single_child_topics(item)
    # Empty string is not a meaningful title — parent's title should be used
    assert result["title"] == "Parent Title"


def test_flatten_preserves_leaf():
    """Leaf items (no children) are unchanged."""
    item = {"title": "Leaf", "metadata": {}, "href": "page.html"}
    result = flatten_single_child_topics(item)
    assert result["title"] == "Leaf"
    assert result["href"] == "page.html"


def test_collect_resources_dangling_identifierref():
    """Dangling identifierref is handled gracefully."""
    with create_zip_with_manifest("manifest_dangling_ref.xml") as zip_path:
        result = parse_imscp_manifest(zip_path)
    org = result["organizations"][0]
    valid_item = next(c for c in org["children"] if c["title"] == "Valid Item")
    assert valid_item.get("href") == "valid.html"
    dangling_item = next(c for c in org["children"] if c["title"] == "Dangling Item")
    assert "href" not in dangling_item


# --- Manifest with bad encoding test ---


def test_manifest_with_bad_encoding():
    """chardet fallback handles non-UTF-8 manifest files."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        # Create a manifest with Latin-1 encoded content
        manifest_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<manifest>
    <metadata>
        <lom>
            <general>
                <title>
                    <langstring xml:lang="de">Einf\xfchrung</langstring>
                </title>
                <language>de</language>
            </general>
        </lom>
    </metadata>
    <organizations>
        <organization>
            <title>Test</title>
        </organization>
    </organizations>
    <resources/>
</manifest>"""
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("imsmanifest.xml", manifest_content)

        result = parse_imscp_manifest(temp_zip_path)
        assert result["metadata"]["title"] == "Einführung"
    finally:
        os.remove(temp_zip_path)


# --- has_imscp_manifest tests ---


def test_has_imscp_manifest_true():
    with create_zip_with_manifest("simple_manifest.xml") as zip_path:
        assert has_imscp_manifest(zip_path) is True


def test_has_imscp_manifest_false():
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("index.html", "<html><body>Hello</body></html>")
        assert has_imscp_manifest(temp_zip_path) is False
    finally:
        os.remove(temp_zip_path)


def test_has_imscp_manifest_nonexistent_file():
    assert has_imscp_manifest("/nonexistent/path.zip") is False


# --- SCORM metadata to content node fields tests ---


def test_metadata_dict_to_content_node_fields_basic():
    """Title and description are mapped."""
    metadata = {"title": "My Course", "description": "Course description"}
    result = metadata_dict_to_content_node_fields(metadata)
    assert result["title"] == "My Course"
    assert result["description"] == "Course description"


def test_metadata_dict_to_content_node_fields_educational():
    """Learning activities and resource types are mapped from SCORM educational metadata."""
    metadata = {
        "learningResourceType": ["exercise", "simulation"],
        "interactivityType": "active",
        "interactivityLevel": "high",
    }
    result = metadata_dict_to_content_node_fields(metadata)
    assert "learning_activities" in result
    assert "resource_types" in result
    assert len(result["learning_activities"]) > 0
    assert len(result["resource_types"]) > 0


def test_metadata_dict_to_content_node_fields_keywords():
    """Keywords are mapped to extra_fields.tags."""
    metadata = {"keyword": ["hummingbirds", "birds"]}
    result = metadata_dict_to_content_node_fields(metadata)
    assert result["tags"] == ["hummingbirds", "birds"]


def test_metadata_dict_to_content_node_fields_keywords_string():
    """Single keyword string is wrapped in a list."""
    metadata = {"keyword": "biology"}
    result = metadata_dict_to_content_node_fields(metadata)
    assert result["tags"] == ["biology"]


def test_metadata_dict_to_content_node_fields_empty():
    """Empty dict returns empty result."""
    result = metadata_dict_to_content_node_fields({})
    assert result == {}


def test_metadata_dict_to_content_node_fields_language():
    """Language code is mapped and normalized."""
    metadata = {"language": "en-US"}
    result = metadata_dict_to_content_node_fields(metadata)
    assert result["language"] == "en"


def test_metadata_dict_to_content_node_fields_difficulty():
    """Easy difficulty infers FOR_BEGINNERS learner need."""
    metadata = {"difficulty": "easy"}
    result = metadata_dict_to_content_node_fields(metadata)
    assert "learner_needs" in result
    assert len(result["learner_needs"]) > 0


# --- Rights/lifecycle integration tests ---


def test_metadata_dict_to_content_node_fields_rights():
    """CC license is inferred from rights_description."""
    from le_utils.constants import licenses

    metadata = {
        "rights_description": "Content is protected under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.",
        "copyrightAndOtherRestrictions": "yes",
    }
    result = metadata_dict_to_content_node_fields(metadata)
    assert result["license"] == licenses.CC_BY_NC_SA


def test_scorm_learning_activities_single_string():
    """Single string learningResourceType should map to one activity, not iterate chars."""
    from ricecooker.utils.SCORM_metadata import map_scorm_to_le_utils_activities
    from le_utils.constants.labels import learning_activities

    result = map_scorm_to_le_utils_activities({"learningResourceType": "exercise"})
    assert result == [learning_activities.PRACTICE]


def test_scorm_resource_types_single_string():
    """Single string learningResourceType should map to one resource type, not iterate chars."""
    from ricecooker.utils.SCORM_metadata import map_scorm_to_educator_resource_types
    from le_utils.constants.labels import resource_type

    result = map_scorm_to_educator_resource_types({"learningResourceType": "exercise"})
    assert result == [resource_type.EXERCISE]


def test_empty_title_raises_manifest_parse_error():
    """Whitespace-only <title> raises ManifestParseError, not AssertionError."""
    from ricecooker.utils.imscp import ManifestParseError

    manifest_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<manifest>
    <metadata><lom><general><title><string>Test</string></title></general></lom></metadata>
    <organizations>
        <organization>
            <title>   </title>
            <item identifier="i1" identifierref="r1"><title>Item</title></item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="r1" type="webcontent" href="index.html">
            <file href="index.html"/>
        </resource>
    </resources>
</manifest>"""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("imsmanifest.xml", manifest_content)
        with pytest.raises(ManifestParseError):
            parse_imscp_manifest(temp_zip_path)
    finally:
        os.remove(temp_zip_path)


def test_metadata_dict_to_content_node_fields_lifecycle():
    """Provider is extracted from lifecycle contribute data."""
    metadata = {
        "contribute": {
            "role": {"value": "publisher"},
            "entity": "BEGIN:VCARD\nVERSION:2.1\nFN:John Doe\nORG:Example Organization\nEND:VCARD",
        }
    }
    result = metadata_dict_to_content_node_fields(metadata)
    assert result["provider"] == "Example Organization"


# --- QTI resource detection tests ---


@pytest.mark.parametrize(
    "resource_type,expected",
    [
        ("imsqti_item_xmlv2p1", True),
        ("imsqti_test_xmlv2p1", True),
        ("imsqti_assessment_xmlv2p1", True),
        ("webcontent", False),
        ("", False),
        (None, False),
        ("associatedcontent/imscc_xmlv1p1/learning-application-resource", False),
    ],
)
def test_is_qti_resource(resource_type, expected):
    assert is_qti_resource(resource_type) is expected


def test_collect_resources_qti():
    """QTI resources get files populated just like webcontent."""
    with create_zip_with_manifest("qti_manifest.xml") as zip_path:
        result = parse_imscp_manifest(zip_path)

    org = result["organizations"][0]
    # Both items reference QTI resources and should have files
    for child in org["children"]:
        assert "files" in child, f"QTI item '{child['title']}' should have files"
        assert len(child["files"]) > 0


def test_collect_resources_mixed():
    """Mixed package: both webcontent and QTI items get files."""
    with create_zip_with_manifest("mixed_manifest.xml") as zip_path:
        result = parse_imscp_manifest(zip_path)

    org = result["organizations"][0]
    lessons = next(c for c in org["children"] if c["title"] == "Lessons")
    quizzes = next(c for c in org["children"] if c["title"] == "Quizzes")

    # Webcontent leaf
    lesson1 = lessons["children"][0]
    assert "files" in lesson1
    assert "lesson1.html" in lesson1["files"]

    # QTI leaves
    for quiz in quizzes["children"]:
        assert "files" in quiz, f"QTI item '{quiz['title']}' should have files"


def test_has_qti_resources_true():
    """Zip with QTI resource types returns True."""
    with create_zip_with_manifest("qti_manifest.xml") as zip_path:
        assert has_qti_resources(zip_path) is True


def test_has_qti_resources_false():
    """Zip with only webcontent returns False."""
    with create_zip_with_manifest("simple_manifest.xml") as zip_path:
        assert has_qti_resources(zip_path) is False


def test_has_qti_resources_mixed():
    """Mixed package with both webcontent and QTI returns True."""
    with create_zip_with_manifest("mixed_manifest.xml") as zip_path:
        assert has_qti_resources(zip_path) is True


def test_has_qti_resources_nonexistent_file():
    assert has_qti_resources("/nonexistent/path.zip") is False


def test_has_qti_resources_bad_zip():
    """Garbage bytes file: has_qti_resources returns False."""
    temp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp.write(b"this is not a zip file at all")
    temp.close()
    try:
        assert has_qti_resources(temp.name) is False
    finally:
        os.remove(temp.name)


def test_has_qti_resources_invalid_manifest():
    """Zip with malformed XML as imsmanifest.xml: has_qti_resources returns False."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("imsmanifest.xml", "<<<not valid xml>>>")
        assert has_qti_resources(temp_zip_path) is False
    finally:
        os.remove(temp_zip_path)


def test_has_qti_resources_manifest_missing_from_zip():
    """Zip without imsmanifest.xml: has_qti_resources returns False."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("index.html", "<html></html>")
        assert has_qti_resources(temp_zip_path) is False
    finally:
        os.remove(temp_zip_path)


def test_collect_resources_qti_preserves_type():
    """QTI items have their resource type preserved in the item dict."""
    with create_zip_with_manifest("qti_manifest.xml") as zip_path:
        result = parse_imscp_manifest(zip_path)

    org = result["organizations"][0]
    for child in org["children"]:
        assert child.get("type") == "imsqti_item_xmlv2p1"


def test_collect_resources_mixed_preserves_types():
    """Mixed items preserve their respective resource types."""
    with create_zip_with_manifest("mixed_manifest.xml") as zip_path:
        result = parse_imscp_manifest(zip_path)

    org = result["organizations"][0]
    lessons = next(c for c in org["children"] if c["title"] == "Lessons")
    quizzes = next(c for c in org["children"] if c["title"] == "Quizzes")

    lesson1 = lessons["children"][0]
    assert lesson1.get("type") == "webcontent"

    quiz1 = quizzes["children"][0]
    assert is_qti_resource(quiz1.get("type", ""))


# --- has_qti_items / has_webcontent_items tests (parsed manifest dict) ---


def test_has_qti_items_pure_qti():
    """has_qti_items returns True for a pure QTI manifest."""
    with create_zip_with_manifest("qti_manifest.xml") as zip_path:
        parsed = parse_imscp_manifest(zip_path)
    assert has_qti_items(parsed) is True


def test_has_qti_items_pure_imscp():
    """has_qti_items returns False for a pure IMSCP (webcontent) manifest."""
    with create_zip_with_manifest("simple_manifest.xml") as zip_path:
        parsed = parse_imscp_manifest(zip_path)
    assert has_qti_items(parsed) is False


def test_has_qti_items_mixed():
    """has_qti_items returns True for a mixed manifest."""
    with create_zip_with_manifest("mixed_manifest.xml") as zip_path:
        parsed = parse_imscp_manifest(zip_path)
    assert has_qti_items(parsed) is True


def test_has_webcontent_items_pure_imscp():
    """has_webcontent_items returns True for a pure IMSCP (webcontent) manifest."""
    with create_zip_with_manifest("simple_manifest.xml") as zip_path:
        parsed = parse_imscp_manifest(zip_path)
    assert has_webcontent_items(parsed) is True


def test_has_webcontent_items_pure_qti():
    """has_webcontent_items returns False for a pure QTI manifest."""
    with create_zip_with_manifest("qti_manifest.xml") as zip_path:
        parsed = parse_imscp_manifest(zip_path)
    assert has_webcontent_items(parsed) is False


def test_has_webcontent_items_mixed():
    """has_webcontent_items returns True for a mixed manifest."""
    with create_zip_with_manifest("mixed_manifest.xml") as zip_path:
        parsed = parse_imscp_manifest(zip_path)
    assert has_webcontent_items(parsed) is True
