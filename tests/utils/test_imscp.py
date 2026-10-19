import os
from xml.etree import ElementTree as ET

import pytest

from ricecooker.utils.encodings import parse_xml
from ricecooker.utils.imscp import parse_imscp_manifest


def _write_manifest(directory, manifest_xml, encoding="utf-8"):
    with open(os.path.join(directory, "imsmanifest.xml"), "w", encoding=encoding) as fh:
        fh.write(manifest_xml)


def _parse_leaf(tmp_path, resources, item_body="", identifierref="RES"):
    """Write a one-item manifest wrapping ``resources`` and return its parsed leaf."""
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
        'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2" identifier="M">'
        '<organizations default="ORG"><organization identifier="ORG"><title>Org</title>'
        '<item identifier="IT" identifierref="{}"><title>Leaf</title>{}</item>'
        "</organization></organizations>"
        "<resources>{}</resources></manifest>".format(
            identifierref, item_body, resources
        ),
    )
    return parse_imscp_manifest(str(tmp_path))["children"][0]["children"][0]


_EXTERNAL_METADATA_MANIFEST = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
    'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2" identifier="M">'
    "<metadata><schema>IMS CONTENT</schema>"
    "<adlcp:location>meta.xml</adlcp:location></metadata>"
    '<organizations default="ORG"><organization identifier="ORG"><title>Org</title>'
    '<item identifier="IT" identifierref="RES"><title>Leaf</title></item>'
    "</organization></organizations>"
    '<resources><resource identifier="RES" type="webcontent" href="p.html">'
    '<file href="p.html"/></resource></resources></manifest>'
)


def _external_lom(encoding, title):
    return (
        f'<?xml version="1.0" encoding="{encoding}"?>'
        '<lom xmlns="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1">'
        f"<general><title><langstring>{title}</langstring></title></general></lom>"
    )


def test_collect_metadata_external_location(tmp_path):
    # An <adlcp:location> under <metadata> points at an external LOM file, which
    # the parser resolves relative to the package directory.
    with open(os.path.join(str(tmp_path), "meta.xml"), "w", encoding="utf-8") as fh:
        fh.write(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<lom xmlns="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1">'
            "<general><title><langstring>External Title</langstring></title>"
            "<keyword><langstring>alpha</langstring></keyword></general></lom>"
        )
    _write_manifest(str(tmp_path), _EXTERNAL_METADATA_MANIFEST)
    metadata = parse_imscp_manifest(str(tmp_path))["metadata"]
    assert metadata["title"] == "External Title"
    assert metadata["keyword"] == "alpha"


def test_external_metadata_in_multibyte_encoding_collected(tmp_path):
    with open(os.path.join(str(tmp_path), "meta.xml"), "wb") as fh:
        fh.write(_external_lom("Shift_JIS", "日本語の題名").encode("shift_jis"))
    _write_manifest(str(tmp_path), _EXTERNAL_METADATA_MANIFEST)
    metadata = parse_imscp_manifest(str(tmp_path))["metadata"]
    assert metadata["title"] == "日本語の題名"


def test_external_metadata_in_unknown_encoding_skipped(tmp_path):
    with open(os.path.join(str(tmp_path), "meta.xml"), "w", encoding="utf-8") as fh:
        fh.write(_external_lom("bogus", "Ignored"))
    _write_manifest(str(tmp_path), _EXTERNAL_METADATA_MANIFEST)
    metadata = parse_imscp_manifest(str(tmp_path))["metadata"]
    assert "title" not in metadata


@pytest.mark.parametrize("encoding", ["Shift_JIS", "MS932"])
def test_manifest_in_multibyte_encoding_parsed(tmp_path, encoding):
    _write_manifest(
        str(tmp_path),
        f'<?xml version="1.0" encoding="{encoding}"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="M">'
        '<organizations><organization identifier="ORG"><title>組織</title>'
        '<item identifier="IT" identifierref="RES"><title>項目</title></item>'
        "</organization></organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="p.html">'
        '<file href="p.html"/></resource></resources></manifest>',
        encoding=encoding,
    )
    organization = parse_imscp_manifest(str(tmp_path))["children"][0]
    assert organization["title"] == "組織"
    assert organization["children"][0]["title"] == "項目"


def test_multibyte_manifest_internal_entity_expanded(tmp_path):
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="Shift_JIS"?>'
        '<!DOCTYPE manifest [<!ENTITY org "組織">]>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="M">'
        '<organizations><organization identifier="ORG"><title>&org;</title>'
        '<item identifier="IT" identifierref="RES"><title>項目</title></item>'
        "</organization></organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="p.html">'
        '<file href="p.html"/></resource></resources></manifest>',
        encoding="shift_jis",
    )
    organization = parse_imscp_manifest(str(tmp_path))["children"][0]
    assert organization["title"] == "組織"


# chardet needs about this much text to name Shift_JIS for the bytes after the first non-UTF-8 byte.
_LONG_JAPANESE_TITLE = (
    "これは日本語で書かれた教材の組織です。学習者のための項目を含みます。"
)


@pytest.mark.parametrize(
    "declaration",
    ['<?xml version="1.0" encoding="UTF-8"?>', ""],
    ids=["utf-8-declared", "undeclared"],
)
def test_manifest_with_undecodable_bytes_recovered(tmp_path, declaration):
    _write_manifest(
        str(tmp_path),
        f"{declaration}"
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="M">'
        '<organizations><organization identifier="ORG">'
        f"<title>{_LONG_JAPANESE_TITLE}</title>"
        '<item identifier="IT" identifierref="RES"><title>項目</title></item>'
        "</organization></organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="p.html">'
        '<file href="p.html"/></resource></resources></manifest>',
        encoding="shift_jis",
    )
    organization = parse_imscp_manifest(str(tmp_path))["children"][0]
    assert organization["title"] == _LONG_JAPANESE_TITLE
    assert organization["children"][0]["title"] == "項目"


@pytest.mark.parametrize(
    "manifest",
    [
        '<?xml version="1.0" encoding="Shift_JIS"?><manifest><title>組織</title>',
        '<?xml version="1.0" encoding="Shift_JIS"?><manifest><title>組織&nbsp;</title></manifest>',
    ],
    ids=["truncated", "undefined-entity"],
)
def test_malformed_multibyte_manifest_raises_parse_error(tmp_path, manifest):
    _write_manifest(str(tmp_path), manifest, encoding="shift_jis")
    with pytest.raises(ET.ParseError):
        parse_imscp_manifest(str(tmp_path))


def test_parse_xml_unencodable_text_raises_parse_error():
    with pytest.raises(ET.ParseError):
        parse_xml("<a>\ud800</a>")


def test_manifest_mislabelled_multibyte_encoding_decoded(tmp_path):
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="Shift_JIS"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="M">'
        '<organizations><organization identifier="ORG"><title>日本語の組織</title>'
        '<item identifier="IT" identifierref="RES"><title>項目</title></item>'
        "</organization></organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="p.html">'
        '<file href="p.html"/></resource></resources></manifest>',
    )
    organization = parse_imscp_manifest(str(tmp_path))["children"][0]
    assert organization["title"] == "日本語の組織"


def test_xml_base_applied_to_index_file(tmp_path):
    # index_file must carry the same xml:base offset as the resource's members,
    # or it resolves to a nonexistent path and the whole resource is dropped.
    # Bases on <resources> and <resource> compose.
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="M">'
        '<organizations><organization identifier="ORG">'
        '<item identifier="IT" identifierref="RES"><title>Leaf</title></item>'
        "</organization></organizations>"
        '<resources xml:base="course/"><resource identifier="RES" type="webcontent" '
        'xml:base="content/" href="start.html"><file href="start.html"/></resource>'
        "</resources></manifest>",
    )
    leaf = parse_imscp_manifest(str(tmp_path))["children"][0]["children"][0]
    assert leaf["index_file"] == "course/content/start.html"
    assert leaf["files"] == ["course/content/start.html"]


def test_qti_resources_listed_without_an_organization(tmp_path):
    # QTI packages have no organization; their resources are found by type.
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsglobal.org/xsd/qti/qtiv3p0/imscp_v1p1" identifier="M">'
        '<organizations/><resources xml:base="qti/">'
        '<resource identifier="T" type="imsqti_test_xmlv3p0" href="t.xml"><file href="t.xml"/></resource>'
        '<resource identifier="W" type="webcontent" href="p.html"><file href="p.html"/></resource>'
        '<resource identifier="A" type="imsqti_item_xmlv3p0" href="items/a.xml"><file href="items/a.xml"/></resource>'
        "</resources></manifest>",
    )
    qti_resources = parse_imscp_manifest(str(tmp_path))["qti_resources"]
    assert [(r["source_id"], r["type"], r["index_file"]) for r in qti_resources] == [
        ("T", "imsqti_test_xmlv3p0", "qti/t.xml"),
        ("A", "imsqti_item_xmlv3p0", "qti/items/a.xml"),
    ]


def test_only_default_organization_read(tmp_path):
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" identifier="M">'
        '<organizations default="B">'
        '<organization identifier="A"><item identifier="IA" identifierref="RES">'
        "<title>A</title></item></organization>"
        '<organization identifier="B"><item identifier="IB" identifierref="RES">'
        "<title>B</title></item></organization>"
        "</organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="p.html">'
        '<file href="p.html"/></resource></resources></manifest>',
    )
    children = parse_imscp_manifest(str(tmp_path))["children"]
    assert [leaf["title"] for leaf in children[0]["children"]] == ["B"]


def test_resource_metadata_used_when_item_has_none(tmp_path):
    leaf = _parse_leaf(
        tmp_path,
        '<resource identifier="RES" type="webcontent" href="p.html">'
        "<metadata><lom><general><keyword><langstring>alpha</langstring>"
        '</keyword></general></lom></metadata><file href="p.html"/></resource>',
    )
    assert leaf["metadata"]["keyword"] == "alpha"


def test_dangling_reference_dropped(tmp_path):
    # An item pointing at a missing resource is left without files rather than
    # crashing; the tree still parses.
    leaf = _parse_leaf(tmp_path, "", identifierref="MISSING")
    assert "files" not in leaf
    assert leaf["source_id"] == "IT"


def test_cyclic_dependency_does_not_recurse_forever(tmp_path):
    # A malformed/untrusted manifest with a <dependency> cycle (A→B→A) must not
    # send file derivation into unbounded recursion; each member appears once.
    leaf = _parse_leaf(
        tmp_path,
        '<resource identifier="A" type="webcontent" href="a.html">'
        '<file href="a.html"/><dependency identifierref="B"/></resource>'
        '<resource identifier="B" type="webcontent" href="b.html">'
        '<file href="b.html"/><dependency identifierref="A"/></resource>',
        identifierref="A",
    )
    assert leaf["files"] == ["a.html", "b.html"]
