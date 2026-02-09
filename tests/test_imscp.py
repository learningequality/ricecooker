"""Tests for IMSCP manifest parsing (ricecooker.utils.imscp)."""
import os
import tempfile
import zipfile
from contextlib import contextmanager

import pytest

from ricecooker.utils.imscp import flatten_single_child_topics
from ricecooker.utils.imscp import has_imscp_manifest
from ricecooker.utils.imscp import parse_imscp_manifest
from ricecooker.utils.SCORM_metadata import metadata_dict_to_content_node_fields


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
IMS_XML_DIR = os.path.join(BASE_PATH, "testcontent", "samples", "ims_xml")


@contextmanager
def create_zip_with_manifest(manifest_filename, *additional_files):
    """Create a temp zip with a manifest and optional additional files."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        manifest_file = os.path.join(IMS_XML_DIR, manifest_filename)
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.write(manifest_file, "imsmanifest.xml")
            for additional_file in additional_files:
                zf.write(os.path.join(IMS_XML_DIR, additional_file), additional_file)
        yield temp_zip_path
    finally:
        try:
            os.remove(temp_zip_path)
        except (FileNotFoundError, OSError):
            pass


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

    result = map_scorm_to_educator_resource_types(
        {"learningResourceType": "exercise"}
    )
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
