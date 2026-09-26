"""QTI 3.0 items: parse them, strip what the item schema cannot validate, and validate them."""

import os
import threading
from functools import lru_cache

from lxml import etree

from ricecooker.utils.imscp import contained_path

QTI3_NAMESPACE = "http://www.imsglobal.org/xsd/imsqtiasi_v3p0"

# Studio's vendored item schema (learningequality/studio@3bdac307), so an item that
# passes here passes Studio's validate_qti_item.
ITEM_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "qti_xsd", "imsqti_itemv3p0p1_v1p0.xsd"
)
# validate() writes to the schema's shared error_log; tree processing is threaded.
_VALIDATION_LOCK = threading.Lock()
# The schema's targetNamespaces: QTI, MathML, SSML, XInclude and xml:.
ITEM_NAMESPACES = frozenset(
    (
        QTI3_NAMESPACE,
        "http://www.w3.org/1998/Math/MathML",
        "http://www.w3.org/2001/10/synthesis",
        "http://www.w3.org/2001/XInclude",
        "http://www.w3.org/XML/1998/namespace",
    )
)
_STYLESHEET_TAG = f"{{{QTI3_NAMESPACE}}}qti-stylesheet"
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


def read_qti3(package_dir, member, tag):
    """Parse ``member`` as a QTI 3.0 ``<tag>``; return its root element.

    Raises ``ValueError`` saying why the file is unusable.
    """
    path = contained_path(package_dir, member)
    if path is None or not os.path.isfile(path):
        raise ValueError("is missing or outside the package")
    try:
        root = etree.parse(path, _PARSER).getroot()
    except etree.XMLSyntaxError as e:
        raise ValueError(f"is not well-formed XML: {e.msg}")
    if root.tag != f"{{{QTI3_NAMESPACE}}}{tag}":
        raise ValueError(f"is not a QTI 3.0 <{tag}> (only QTI 3.0 is supported)")
    return root


def strip_unschematized(item):
    """Drop markup the item schema cannot validate from ``item``, in place.

    That is ``<qti-stylesheet>``, which Kolibri does not render, and elements and
    attributes outside the schema's namespaces, which its ``any`` wildcards reject.
    """
    for elem in list(item.iter(etree.Element)):
        if elem.tag == _STYLESHEET_TAG or _is_foreign(elem.tag):
            _remove(elem)
            continue
        for name in [name for name in elem.attrib if _is_foreign(name)]:
            del elem.attrib[name]
    etree.cleanup_namespaces(item)


def _is_foreign(name):
    namespace = etree.QName(name).namespace
    return namespace is not None and namespace not in ITEM_NAMESPACES


def _remove(elem):
    """Remove ``elem`` and its subtree, keeping its tail text."""
    parent = elem.getparent()
    if elem.tail:
        previous = elem.getprevious()
        if previous is None:
            parent.text = (parent.text or "") + elem.tail
        else:
            previous.tail = (previous.tail or "") + elem.tail
    parent.remove(elem)


@lru_cache(maxsize=1)
def _item_schema():
    return etree.XMLSchema(etree.parse(ITEM_SCHEMA_PATH))


def validate_qti_item(item):
    """Raise ``ValueError`` naming the first schema error if ``item`` is not a valid QTI 3.0 item."""
    schema = _item_schema()
    with _VALIDATION_LOCK:
        if schema.validate(item):
            return
        error = schema.error_log[0]
    raise ValueError(f"fails the QTI 3.0 schema at line {error.line}: {error.message}")
