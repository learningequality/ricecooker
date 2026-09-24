"""Parse an extracted IMS Content Package (``imsmanifest.xml``) into a tree of dicts.

Ported from ``learningequality/imscp`` ``core.py`` to stdlib
:mod:`xml.etree.ElementTree`. Manifests declare varied default namespaces
(``imscp_rootv1p1p2``, ``imscp_v1p1``), so every ``find``/``findall`` uses a
``{*}`` wildcard rather than a fixed namespace map.
"""

import io
import logging
import os
import posixpath
import re
import shutil
from collections import deque
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import chardet

from ricecooker.utils.references import mapper_for
from ricecooker.utils.references import resolve_reference
from ricecooker.utils.references import split_reference
from ricecooker.utils.SCORM_metadata import metadata_dict_to_content_node_fields

LOGGER = logging.getLogger(__name__)

XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

QTI_RESOURCE_TYPE_PREFIX = "imsqti_"

# The IMS Content Package manifest, always at the root of the package.
IMSCP_MANIFEST = "imsmanifest.xml"

# LOM sections and the fields lifted out of each, keyed by LOM element name.
LOM_METADATA_KEYS = {
    "general": ["title", "description", "language", "keyword"],
    "rights": ["copyrightAndOtherRestrictions", "description"],
    "educational": [
        "interactivityType",
        "interactivityLevel",
        "learningResourceType",
        "intendedEndUserRole",
        "difficulty",
    ],
    "lifeCycle": ["contribute"],
}


def is_qti_resource(resource_type):
    """True when ``resource_type`` names a QTI resource (spec-defined ``imsqti_`` prefix)."""
    return bool(resource_type) and resource_type.startswith(QTI_RESOURCE_TYPE_PREFIX)


def parse_imscp_manifest(ims_dir):
    """Parse ``imsmanifest.xml`` in ``ims_dir`` into the manifest tree.

    Returns ``{"metadata", "children": [node, ...], "qti_resources"}``
    where each ``node`` is a topic (``{"source_id", "title", "children"}``) or a
    webcontent leaf (``{"source_id", "title", "type", "index_file", "href",
    "files"}``). ``files`` are archive-member paths relative to ``ims_dir``.
    ``qti_resources`` lists every QTI resource as a leaf, in manifest order,
    whether or not an organization references it.
    Only the default organization is read; the others restructure the same resources.
    """
    root = _read_manifest(os.path.join(ims_dir, IMSCP_MANIFEST))

    metadata = collect_metadata(root, ims_dir)

    resources_elem = root.find("{*}resources")
    resources = {}
    if resources_elem is not None:
        outer_base = (root.get(XML_BASE) or "") + (resources_elem.get(XML_BASE) or "")
        for resource in resources_elem.findall("{*}resource"):
            # Fold the enclosing bases in, so each resource carries its full offset.
            resource.set(XML_BASE, outer_base + (resource.get(XML_BASE) or ""))
            resources[resource.get("identifier")] = resource

    children = []
    org = _default_organization(root)
    if org is not None:
        node = _walk_items(org, ims_dir)
        _collect_resources(node, resources, ims_dir)
        children.append(node)

    qti_resources = [
        _resolve_resource({"source_id": identifier}, resource, resources, ims_dir)
        for identifier, resource in resources.items()
        if is_qti_resource(resource.get("type"))
    ]

    return {"metadata": metadata, "children": children, "qti_resources": qti_resources}


def _default_organization(root):
    """The ``<organization>`` named by ``organizations/@default``, else the first."""
    organizations = root.find("{*}organizations")
    if organizations is None:
        return None
    orgs = organizations.findall("{*}organization")
    default = organizations.get("default")
    return next(
        (o for o in orgs if o.get("identifier") == default),
        orgs[0] if orgs else None,
    )


def _read_manifest(manifest_path):
    """Parse the manifest, falling back to detected encoding on a parse error."""
    try:
        return ET.parse(manifest_path).getroot()
    except ET.ParseError:
        # Some manifests declare UTF-8 but contain other-encoded bytes; detect the
        # real encoding, decode, and re-parse from re-encoded UTF-8 bytes.
        with open(manifest_path, "rb") as f:
            data = f.read()
        encoding = chardet.detect(data)["encoding"]
        if encoding is None:
            # Nothing to re-decode from; the manifest is simply not parseable.
            raise
        return ET.parse(io.BytesIO(data.decode(encoding).encode("utf-8"))).getroot()


def _strip_ns(key):
    """Strip a ``{namespace}`` prefix off an attribute key."""
    return re.sub(r"^\{.*\}", "", key)


def _lom_children(elem, name):
    """``elem``'s children named ``name``, any namespace or case.

    IEEE LOM names are camelCase (``lifeCycle``); IMS MD 1.2 lowercases them.
    """
    name = name.lower()
    return [
        child
        for child in elem
        if isinstance(child.tag, str) and _strip_ns(child.tag).lower() == name
    ]


def _lom_child(elem, name):
    return next(iter(_lom_children(elem, name)), None)


def _href_path(href):
    """The package path a manifest ``href`` (a URI reference) names."""
    return unquote(split_reference(href)[0])


def _element_text(elem):
    """Concatenate all descendant text/tail (ignoring ``<br>``), stripped."""
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def contained_path(root, member):
    """Resolve ``member`` under ``root``; return the path, or None if it escapes.

    Manifest hrefs, file paths and metadata locations are all untrusted.
    """
    root_abs = os.path.abspath(root)
    target = os.path.abspath(os.path.join(root_abs, member))
    if target != root_abs and not target.startswith(root_abs + os.sep):
        return None
    return target


def _lom_text(elem):
    """The stripped text of a LOM element, or None when empty."""
    return (
        elem.text.strip()
        if elem is not None and elem.text and elem.text.strip()
        else None
    )


def _extract_lom_text(elem, preferred_language):
    """Read text from a LOM field, handling its several shapes.

    Handles ``<string language="en">``/``<langstring xml:lang="en">`` (returning a
    preferred-language match, the single value, or a list), ``<source>/<value>``
    pairs, and bare element text.
    """
    strings = elem.findall("{*}string") or elem.findall("{*}langstring")
    if strings:
        if preferred_language is not None:
            for s in strings:
                lang = s.get("language", "") or s.get(XML_LANG, "")
                if lang.startswith(preferred_language):
                    return _lom_text(s)
        if len(strings) == 1:
            return _lom_text(strings[0])
        return [_lom_text(s) for s in strings]

    # A vocabulary term is ``<value>[<langstring>]term...``; recurse so the term
    # text is read, not the whitespace around it.
    value = elem.find("{*}value")
    if value is not None:
        return _extract_lom_text(value, preferred_language)

    return _lom_text(elem)


def _extract_contribute(contrib_elem):
    """Extract a lifeCycle ``<contribute>`` entry as ``{"role", "entity"}``."""
    result = {}
    role = _lom_child(contrib_elem, "role")
    if role is not None:
        # The role vocabulary term sits in ``<value>`` (bare or langstring-wrapped).
        role_value = _extract_lom_text(role, None)
        if role_value:
            result["role"] = role_value
    # IMS MD 1.2 wraps the vCard as ``<centity><vcard>``.
    entity = _lom_child(contrib_elem, "entity")
    centity = _lom_child(contrib_elem, "centity")
    if entity is None and centity is not None:
        entity = _lom_child(centity, "vcard")
    if entity is not None and entity.text:
        result["entity"] = entity.text
    return result


def _get_lom_section(metadata_elem, tag):
    """The LOM ``<tag>`` section, whether wrapped in ``<lom>`` or bare."""
    lom = _lom_child(metadata_elem, "lom")
    return _lom_child(metadata_elem if lom is None else lom, tag)


def _detect_language(metadata_elem):
    """The preferred language declared in LOM ``<general><language>``."""
    general = _get_lom_section(metadata_elem, "general")
    if general is not None:
        return _lom_text(_lom_child(general, "language"))
    return None


def _resolve_metadata_elem(elem, ims_dir):
    """The ``<metadata>`` of ``elem``, following an external ``adlcp:location`` ref."""
    metadata_elem = elem.find("{*}metadata")
    if metadata_elem is None:
        return None
    location = metadata_elem.find("{*}location")
    if location is not None and location.text:
        ext_path = contained_path(ims_dir, location.text.strip())
        if ext_path and os.path.isfile(ext_path):
            try:
                return ET.parse(ext_path).getroot()
            except ET.ParseError:
                LOGGER.warning(
                    "IMSCP: could not parse external metadata %s", location.text
                )
    return metadata_elem


def _collect_field(section, field, preferred_language):
    """The value of LOM ``field`` in ``section``: scalar when single, list when repeated."""
    elems = _lom_children(section, field)
    if not elems:
        return None
    if field == "contribute":
        values = [_extract_contribute(e) for e in elems]
    else:
        values = [_extract_lom_text(e, preferred_language) for e in elems]
    return values[0] if len(values) == 1 else values


def collect_metadata(elem, ims_dir):
    """Extract the raw LOM metadata dict from ``elem``'s ``<metadata>``.

    Covers the sections named in :data:`LOM_METADATA_KEYS`; mapping onto
    content-node fields is :mod:`ricecooker.utils.SCORM_metadata`'s job.
    """
    metadata_elem = _resolve_metadata_elem(elem, ims_dir)
    if metadata_elem is None:
        return {}

    preferred_language = _detect_language(metadata_elem)

    metadata = {}
    for tag, fields in LOM_METADATA_KEYS.items():
        section = _get_lom_section(metadata_elem, tag)
        if section is None:
            continue
        for field in fields:
            value = _collect_field(section, field, preferred_language)
            if value is not None:
                # Prefix rights fields so ``rights/description`` does not collide
                # with ``general/description``.
                key = "rights_" + field if tag == "rights" else field
                metadata[key] = value
    return metadata


def _walk_items(elem, ims_dir):
    """Build an item/topic dict from ``elem`` and recurse into child ``<item>``s."""
    node = {_strip_ns(k): v for k, v in elem.attrib.items()}

    title = _element_text(elem.find("{*}title"))
    if title:
        node["title"] = title

    # A child element, not an attribute, so the attrib copy above misses it.
    mastery = _element_text(elem.find("{*}masteryscore"))
    if mastery:
        node["masteryscore"] = mastery

    metadata = collect_metadata(elem, ims_dir)
    if metadata:
        node["metadata"] = metadata

    children = [_walk_items(item, ims_dir) for item in elem.findall("{*}item")]
    if children:
        node["children"] = children

    return node


def _collect_resources(item, resources, ims_dir, index=1):
    """Resolve resource references onto items; recurse into topics.

    ``index`` is the item's 1-based sibling position, for the ``item{n}``
    source_id fallback when its identifier is blank.
    """
    item["source_id"] = item.get("identifier") or "item{}".format(index)

    resource = None
    if item.get("identifierref"):
        resource = resources.get(item["identifierref"])
        if resource is None:
            LOGGER.warning(
                "IMSCP: item %s references missing resource %s",
                item["source_id"],
                item["identifierref"],
            )

    children = item.get("children")
    if children:
        for child_index, child in enumerate(children, start=1):
            _collect_resources(child, resources, ims_dir, child_index)
        if resource is not None:
            # A topic item's own page becomes its first leaf.
            page = {"source_id": item["source_id"] + "-page"}
            if item.get("title"):
                page["title"] = item["title"]
            _resolve_resource(page, resource, resources, ims_dir)
            children.insert(0, page)
    elif resource is not None:
        _resolve_resource(item, resource, resources, ims_dir)


def _resolve_resource(item, resource, resources, ims_dir):
    """Copy ``resource``'s type, index, files and metadata onto leaf ``item``."""
    # The item's own attributes win — a resource carries its own
    # ``identifier``, which must not displace the item's identity.
    for key, value in resource.attrib.items():
        item.setdefault(_strip_ns(key), value)
    if "metadata" not in item:
        metadata = collect_metadata(resource, ims_dir)
        if metadata:
            item["metadata"] = metadata
    # Other resource types are rejected downstream.
    resource_type = resource.get("type")
    if resource_type == "webcontent" or is_qti_resource(resource_type):
        href = resource.get("href")
        if href:
            item["index_file"] = (resource.get(XML_BASE) or "") + _href_path(href)
    if resource_type == "webcontent":
        item["files"] = _derive_files(resource, resources)
    return item


def _derive_files(resource, resources, seen=None, visited=None):
    """Own ``<file>`` members plus flattened ``<dependency>`` files, order-preserving."""
    if seen is None:
        seen = set()
    # Guards against a cyclic <dependency> chain.
    if visited is None:
        visited = set()
    identifier = resource.get("identifier")
    if identifier in visited:
        return []
    visited.add(identifier)

    base = resource.get(XML_BASE) or ""
    files = []
    for fe in resource.findall("{*}file"):
        href = fe.get("href")
        if not href:
            continue
        path = base + _href_path(href)
        if path not in seen:
            seen.add(path)
            files.append(path)

    for dep in resource.findall("{*}dependency"):
        dep_ref = dep.get("identifierref")
        dep_resource = resources.get(dep_ref)
        if dep_resource is None:
            LOGGER.warning(
                "IMSCP: resource %s depends on missing resource %s",
                identifier,
                dep_ref,
            )
            continue
        files.extend(_derive_files(dep_resource, resources, seen, visited))

    return files


def lom_content_fields(node_dict):
    """Map a parsed node's raw LOM ``metadata`` to content-node fields."""
    return metadata_dict_to_content_node_fields(node_dict.get("metadata") or {})


def node_content_fields(node_dict):
    """A parsed node's ``source_id`` and ``title`` over its LOM-derived fields."""
    fields = lom_content_fields(node_dict)
    source_id = node_dict["source_id"]
    title = node_dict.get("title") or fields.get("title") or source_id
    return {**fields, "source_id": source_id, "title": title}


def collapse_single_children(node):
    """Collapse a built tree to its minimal hierarchy.

    A folder holding one child is replaced by that child, which fills its missing
    fields from the folder's. Returns what replaces ``node``.
    """
    if "children" not in node:
        return node
    node["children"] = [collapse_single_children(child) for child in node["children"]]
    if len(node["children"]) != 1:
        return node
    (only_child,) = node["children"]
    for key, value in node.items():
        if key not in ("children", "source_id"):
            only_child.setdefault(key, value)
    return only_child


class IMSCPPackage:
    """An extracted package, resolving which of its files each resource needs.

    A resource's ``<file>`` list is under-declared often enough that the assets
    its members reference are included too, bounded to files present in the package.
    Navigation links are not followed, so a leaf never absorbs what it links to.
    """

    def __init__(self, directory):
        self.directory = directory
        # Shared assets are in many leaves' closures; the package never changes.
        self._references = {}

    def closure(self, members):
        """``members`` and the package files they reference, transitively, in discovery order."""
        found = {}
        pending = deque()
        for member in members:
            self._add_member(member, found, pending)
        while pending:
            member = pending.popleft()
            for path in self.references(member) or ():
                self._add_member(path, found, pending)
        return list(found)

    def copy(self, paths, dest_dir):
        """Copy each package member in ``paths`` (member -> dest path) under ``dest_dir``."""
        for member, path in paths.items():
            dst = contained_path(dest_dir, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(contained_path(self.directory, member), dst)

    def references(self, member):
        """The package-local paths an HTML/CSS ``member`` references; None when unreadable."""
        if member not in self._references:
            self._references[member] = self._extract_references(member)
        return self._references[member]

    def _add_member(self, member, found, pending):
        member = posixpath.normpath(member.replace("\\", "/"))
        if member in found:
            return
        # Including the manifest would make the leaf a package, decomposing forever.
        if member == IMSCP_MANIFEST:
            return
        # Manifest paths are untrusted: reject a ``../`` escape.
        src = contained_path(self.directory, member)
        if src is None or not os.path.isfile(src):
            return
        found[member] = None
        pending.append(member)

    def _extract_references(self, member):
        mapper = mapper_for(member)
        if mapper is None:
            return []
        try:
            with open(contained_path(self.directory, member), encoding="utf-8") as fh:
                content = fh.read()
        except (OSError, UnicodeDecodeError):
            return None
        paths = (resolve_reference(member, ref) for ref in mapper.extract(content))
        return [path for path in paths if path is not None]
