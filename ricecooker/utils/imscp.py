"""Parse an extracted IMS Content Package (``imsmanifest.xml``) into a tree of dicts.

Ported from ``learningequality/imscp`` ``core.py`` to stdlib
:mod:`xml.etree.ElementTree`. Manifests declare varied default namespaces
(``imscp_rootv1p1p2``, ``imscp_v1p1``), so every ``find``/``findall`` uses a
``{*}`` wildcard rather than a fixed namespace map.
"""

import io
import os
import re
from xml.etree import ElementTree as ET

import chardet

XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"


def parse_imscp_manifest(ims_dir):
    """Parse ``imsmanifest.xml`` in ``ims_dir`` into the manifest tree.

    Returns ``{"identifier", "title", "metadata", "children": [node, ...]}``
    where each ``node`` is a topic (``{"source_id", "title", "children"}``) or a
    webcontent leaf (``{"source_id", "title", "type", "index_file", "href",
    "scormtype", "files"}``). ``files`` are archive-member paths relative to
    ``ims_dir``.
    """
    root = _read_manifest(os.path.join(ims_dir, "imsmanifest.xml"))

    metadata = _collect_general_metadata(root.find("{*}metadata"))

    resources = {
        r.get("identifier"): r for r in root.findall("{*}resources/{*}resource")
    }

    children = []
    for org in root.findall("{*}organizations/{*}organization"):
        node = _walk_items(org)
        _collect_resources(node, resources)
        children.append(node)

    return {
        "identifier": root.get("identifier"),
        "title": metadata.get("title"),
        "metadata": metadata,
        "children": children,
    }


def _read_manifest(manifest_path):
    """Parse the manifest, falling back to detected encoding on a parse error."""
    try:
        return ET.parse(manifest_path).getroot()
    except ET.ParseError:
        # Some manifests declare UTF-8 but contain other-encoded bytes; detect the
        # real encoding, decode, and re-parse from re-encoded UTF-8 bytes.
        with open(manifest_path, "rb") as f:
            data = f.read()
        info = chardet.detect(data)
        data = data.decode(info["encoding"])
        return ET.parse(io.BytesIO(data.encode("utf-8"))).getroot()


def _strip_ns(key):
    """Strip a ``{namespace}`` prefix off an attribute key."""
    return re.sub(r"^\{.*\}", "", key)


def _element_text(elem):
    """Concatenate all descendant text/tail (ignoring ``<br>``), stripped."""
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def _collect_general_metadata(metadata_elem):
    """Extract ``title``/``description``/``language`` from LOM ``<general>``."""
    metadata = {}
    if metadata_elem is None:
        return metadata
    general = metadata_elem.find("{*}lom/{*}general")
    if general is None:
        return metadata
    for key in ("title", "description", "language"):
        text = _element_text(general.find("{*}" + key))
        if text:
            metadata[key] = text
    return metadata


def _walk_items(elem):
    """Build an item/topic dict from ``elem`` and recurse into child ``<item>``s."""
    node = {_strip_ns(k): v for k, v in elem.attrib.items()}

    title = _element_text(elem.find("{*}title"))
    if title:
        node["title"] = title

    # ``<adlcp:masteryscore>`` is a child element of the item (not an attribute),
    # so it is not captured by the attrib copy above. Surface it for the
    # assessment classifier, which treats a mastery score as an exercise signal.
    mastery = _element_text(elem.find("{*}masteryscore"))
    if mastery:
        node["masteryscore"] = mastery

    children = [_walk_items(item) for item in elem.findall("{*}item")]
    if children:
        node["children"] = children

    return node


def _collect_resources(item, resources, index=1):
    """Resolve resource references onto leaf items; recurse into topics.

    ``index`` is the item's 1-based position among its siblings, used for the
    ``item{n}`` source_id fallback when an identifier is blank (ported from
    legacy ricecooker_utils, not core.py).
    """
    # The item ``identifier`` is the node's source_id; fall back to ``item{n}``.
    item["source_id"] = item.get("identifier") or "item{}".format(index)

    children = item.get("children")
    if children:
        for child_index, child in enumerate(children, start=1):
            _collect_resources(child, resources, child_index)
    elif item.get("identifierref"):
        resource = resources.get(item["identifierref"])
        if resource is not None:
            for key, value in resource.attrib.items():
                item[_strip_ns(key)] = value
            if resource.get("type") == "webcontent":
                href = resource.get("href")
                if href:
                    # ``index_file`` must carry the same ``xml:base`` offset that
                    # _derive_files applies to the resource's members, or it will
                    # not resolve to a real extracted path.
                    item["index_file"] = (resource.get(XML_BASE) or "") + href
                item["files"] = _derive_files(resource, resources)
                item.setdefault("scormtype", None)


def _derive_files(resource, resources, seen=None):
    """Own ``<file>`` members plus flattened ``<dependency>`` files, order-preserving."""
    if seen is None:
        seen = set()

    base = resource.get(XML_BASE) or ""
    files = []
    for fe in resource.findall("{*}file"):
        href = fe.get("href")
        if not href:
            continue
        path = base + href
        if path not in seen:
            seen.add(path)
            files.append(path)

    for dep in resource.findall("{*}dependency"):
        dep_resource = resources.get(dep.get("identifierref"))
        if dep_resource is not None:
            files.extend(_derive_files(dep_resource, resources, seen))

    return files
