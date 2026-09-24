import os

from ricecooker.utils.imscp import parse_imscp_manifest


def _write_manifest(directory, manifest_xml):
    with open(os.path.join(directory, "imsmanifest.xml"), "w", encoding="utf-8") as fh:
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
    _write_manifest(
        str(tmp_path),
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" '
        'xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2" identifier="M">'
        "<metadata><schema>IMS CONTENT</schema>"
        "<adlcp:location>meta.xml</adlcp:location></metadata>"
        '<organizations default="ORG"><organization identifier="ORG"><title>Org</title>'
        '<item identifier="IT" identifierref="RES"><title>Leaf</title></item>'
        "</organization></organizations>"
        '<resources><resource identifier="RES" type="webcontent" href="p.html">'
        '<file href="p.html"/></resource></resources></manifest>',
    )
    metadata = parse_imscp_manifest(str(tmp_path))["metadata"]
    assert metadata["title"] == "External Title"
    # A lone <keyword> collects as a single value; the mapping normalizes to a list.
    assert metadata["keyword"] == "alpha"


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
