"""
Standalone IMSCP manifest parsing utilities.

Used by the file pipeline to parse imsmanifest.xml from IMSCP zip files.
"""
import io
import logging
import re
import zipfile

import chardet
from lxml import etree

from ricecooker.utils.SCORM_metadata import imscp_metadata_keys

logger = logging.getLogger(__name__)


class ManifestParseError(Exception):
    """Raised when an imsmanifest.xml cannot be parsed."""


def strip_ns_prefix(tree):
    """Strip namespace prefixes from an LXML tree.
    From https://stackoverflow.com/a/30233635
    """
    for element in tree.xpath("descendant-or-self::*[namespace-uri()!='']"):
        element.tag = etree.QName(element).localname


def _get_elem_for_tag(root, tag):
    elem = root.find("lom/%s" % tag)
    if elem is not None:
        return elem
    return root.find(tag)


def _extract_lom_text(elem, preferred_language):
    """Extract text from a LOM element using direct lxml traversal.

    Handles common LOM XML patterns:
      - <field><string language="en">text</string></field>
      - <field><langstring xml:lang="en">text</langstring></field>
      - <field><source>LOMv1.0</source><value>text</value></field>
      - <field>plain text</field>
    """
    strings = elem.findall("string") or elem.findall("langstring")
    if strings:
        if preferred_language is not None:
            for s in strings:
                lang = s.get("language", "") or s.get(
                    "{http://www.w3.org/XML/1998/namespace}lang", ""
                )
                if lang.startswith(preferred_language):
                    return s.text
        if len(strings) == 1:
            return strings[0].text
        return [s.text for s in strings]

    value_elem = elem.find("value")
    if value_elem is not None:
        return value_elem.text

    return elem.text.strip() if elem.text and elem.text.strip() else None


def _extract_contribute(contrib_elem):
    """Extract a lifeCycle contribute entry as a dict with role and entity."""
    result = {}
    role_elem = contrib_elem.find("role")
    if role_elem is not None:
        value_elem = role_elem.find("value")
        if value_elem is not None:
            result["role"] = {"value": value_elem.text}
    entity_elem = contrib_elem.find("entity")
    if entity_elem is not None and entity_elem.text:
        result["entity"] = entity_elem.text
    return result


def _resolve_metadata_elem(root, zip_file):
    """Find and resolve the metadata element, following external references."""
    metadata_elem = root.find("metadata", root.nsmap)
    if metadata_elem is None:
        return None

    external_ref = metadata_elem.find(
        "adlcp:location",
        namespaces={"adlcp": "http://www.adlnet.org/xsd/adlcp_v1p3"},
    )
    if external_ref is not None and zip_file is not None:
        with zip_file.open(external_ref.text) as external_file:
            metadata_elem = etree.parse(external_file).getroot()

    strip_ns_prefix(metadata_elem)
    return metadata_elem


def _detect_language(metadata_elem):
    """Detect the language from the general section of a metadata element."""
    gen_elem = _get_elem_for_tag(metadata_elem, "general")
    if gen_elem is not None:
        lang_elem = gen_elem.find("language")
        if lang_elem is not None and lang_elem.text:
            return lang_elem.text.strip()
    return None


def _collect_field(elem, tag, field, preferred_language):
    """Extract a single field from a LOM section element.

    Returns (key, value) or None if the field is not present.
    """
    if field == "contribute":
        contrib_elems = elem.findall("contribute")
        if len(contrib_elems) == 1:
            return ("contribute", _extract_contribute(contrib_elems[0]))
        elif contrib_elems:
            return ("contribute", [_extract_contribute(c) for c in contrib_elems])
        return None

    field_elems = elem.findall(field)
    if not field_elems:
        return None
    # Prefix rights fields to avoid collision with general.description
    key = "rights_{}".format(field) if tag == "rights" else field
    if len(field_elems) == 1:
        return (key, _extract_lom_text(field_elems[0], preferred_language))
    return (key, [_extract_lom_text(fe, preferred_language) for fe in field_elems])


def collect_metadata(root, zip_file=None, language=None):
    """Extract LOM metadata from a manifest element.

    Args:
        root: lxml Element (manifest or organization root)
        zip_file: open ZipFile for resolving external metadata refs
        language: preferred language code

    Returns:
        dict of metadata fields
    """
    metadata_elem = _resolve_metadata_elem(root, zip_file)
    if metadata_elem is None:
        return {}

    preferred_language = language or _detect_language(metadata_elem)

    metadata_dict = {}
    for tag, fields in imscp_metadata_keys.items():
        elem = _get_elem_for_tag(metadata_elem, tag)
        if elem is None:
            continue
        for field in fields:
            result = _collect_field(elem, tag, field, preferred_language)
            if result is not None:
                metadata_dict[result[0]] = result[1]

    return metadata_dict


def parse_manifest_from_zip(zf):
    """Parse imsmanifest.xml from an already-open ZipFile, with chardet fallback.

    Args:
        zf: an open zipfile.ZipFile instance

    Returns:
        lxml Element root of the manifest
    """
    try:
        with zf.open("imsmanifest.xml") as manifest_file:
            return etree.parse(manifest_file).getroot()
    except (etree.XMLSyntaxError, OSError):
        pass

    # Handle XML files that are marked as UTF-8 but have non-UTF-8 chars.
    # Detect the real encoding with chardet and re-encode as UTF-8.
    try:
        f = zf.open("imsmanifest.xml", "r")
        data = f.read()
        f.close()

        info = chardet.detect(data)
        encoding = info["encoding"] or "utf-8"
        data = data.decode(encoding)
        return etree.parse(io.BytesIO(data.encode("utf-8"))).getroot()
    except (etree.XMLSyntaxError, OSError, UnicodeDecodeError) as e:
        raise ManifestParseError(str(e)) from e


def get_manifest(zip_path):
    """Parse imsmanifest.xml from a zip file path, with chardet fallback.

    Args:
        zip_path: path to the zip file

    Returns:
        lxml Element root of the manifest
    """
    with zipfile.ZipFile(zip_path) as zf:
        return parse_manifest_from_zip(zf)


def walk_items(root, zip_file=None, language=None):
    """Recursively walk item elements in a manifest, collecting metadata.

    Args:
        root: lxml Element for an organization or item
        zip_file: open ZipFile for resolving external metadata refs
        language: preferred language code

    Returns:
        dict with title, metadata, children, and item attributes
    """
    root_dict = dict(root.items())

    title_elem = root.find("title", root.nsmap)
    if title_elem is not None:
        text = ""
        for child in title_elem.iter():
            if child.text:
                text += child.text
            if child.tail:
                text += child.tail
        if not text.strip():
            raise ManifestParseError(
                "Title element has no title: {}".format(
                    etree.tostring(title_elem, pretty_print=True)
                )
            )
        root_dict["title"] = text.strip()

    root_dict["metadata"] = collect_metadata(root, zip_file=zip_file, language=language)

    children = []
    for item in root.findall("item", root.nsmap):
        children.append(walk_items(item, zip_file=zip_file, language=language))

    if children:
        root_dict["children"] = children

    return root_dict


def derive_content_files_dict(resource_elem, resources_dict):
    """Collect all file paths referenced by a resource element, including dependencies."""
    nsmap = resource_elem.nsmap
    file_elements = resource_elem.findall("file", nsmap)
    base = resource_elem.get("{http://www.w3.org/XML/1998/namespace}base") or ""
    file_paths = [base + fe.get("href") for fe in file_elements]
    dep_elements = resource_elem.findall("dependency", nsmap)
    dep_paths = []
    for de in dep_elements:
        dep_ref = de.get("identifierref")
        dre = resources_dict.get(dep_ref)
        if dre is None:
            logger.warning("Dangling dependency identifierref: %s", dep_ref)
            continue
        dep_paths.extend(derive_content_files_dict(dre, resources_dict))
    return file_paths + dep_paths


def collect_resources(item, resources_dict):
    """Link items to their resource data (href, type, files).

    Modifies item dict in-place.
    """
    if item.get("children"):
        for child in item["children"]:
            collect_resources(child, resources_dict)
    elif item.get("identifierref"):
        resource_elem = resources_dict.get(item["identifierref"])
        if resource_elem is None:
            logger.warning("Dangling identifierref: %s", item["identifierref"])
            return

        for key, value in resource_elem.items():
            key_stripped = re.sub("^{.*}", "", key)
            if key_stripped not in item:
                item[key_stripped] = value

        if resource_elem.get("type") == "webcontent":
            item["files"] = derive_content_files_dict(resource_elem, resources_dict)


def flatten_single_child_topics(item):
    """Collapse single-child topic chains.

    When a topic has exactly one child that is also a topic (has children),
    merge them by replacing the parent with the child, keeping the parent's
    title only if the child doesn't have one.

    Returns the (possibly modified) item.
    """
    if "children" not in item:
        return item

    # First flatten all children recursively
    item["children"] = [
        flatten_single_child_topics(child) for child in item["children"]
    ]

    # Then check if this item has exactly one child that is also a topic
    if len(item["children"]) == 1:
        only_child = item["children"][0]
        if "children" in only_child:
            # Merge: keep child's structure but preserve parent's metadata if richer
            if not only_child.get("metadata"):
                only_child["metadata"] = item.get("metadata", {})
            return only_child

    return item


def parse_imscp_manifest(zip_path, language=None):
    """Parse an IMSCP manifest from a zip file.

    Top-level entry point that opens the zip, parses the manifest XML,
    collects metadata and organization tree, links resources,
    and optionally flattens single-child topic chains.

    Args:
        zip_path: path to the IMSCP zip file
        language: preferred language code for metadata extraction

    Returns:
        dict with keys:
            - identifier: manifest identifier string
            - metadata: dict of LOM metadata fields
            - organizations: list of organization dicts with nested items
    """
    manifest = get_manifest(zip_path)
    nsmap = manifest.nsmap

    with zipfile.ZipFile(zip_path) as zf:
        metadata = collect_metadata(manifest, zip_file=zf, language=language)

        resources_elem = manifest.find("resources", nsmap)
        resources_dict = dict((r.get("identifier"), r) for r in resources_elem)

        organizations = []
        for org_elem in manifest.findall("organizations/organization", nsmap):
            item_tree = walk_items(org_elem, zip_file=zf, language=language)
            collect_resources(item_tree, resources_dict)
            item_tree = flatten_single_child_topics(item_tree)
            organizations.append(item_tree)

    return {
        "identifier": manifest.get("identifier"),
        "metadata": metadata,
        "organizations": organizations,
    }


def has_imscp_manifest(zip_path):
    """Check whether a zip file contains imsmanifest.xml.

    Args:
        zip_path: path to the zip file

    Returns:
        bool
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return "imsmanifest.xml" in zf.namelist()
    except (zipfile.BadZipFile, FileNotFoundError):
        return False
