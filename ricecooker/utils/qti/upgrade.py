"""Read QTI files, converting other QTI versions to QTI 3.0."""

import os
import re
from functools import lru_cache

from lxml import etree

from ricecooker.utils.imscp import contained_path
from ricecooker.utils.qti.items import item_vocabulary
from ricecooker.utils.qti.items import parse_qti
from ricecooker.utils.qti.items import QTI3_NAMESPACE
from ricecooker.utils.qti.items import remove_element

_CONTENT_BODY_TAG = f"{{{QTI3_NAMESPACE}}}qti-content-body"
_RUBRIC_BLOCK_TAG = f"{{{QTI3_NAMESPACE}}}qti-rubric-block"
# 3.0 holds these elements' content in a <qti-content-body>; 2.x holds it directly.
_CONTENT_BODY_PARENTS = tuple(
    f"{{{QTI3_NAMESPACE}}}{name}"
    for name in (
        "qti-modal-feedback",
        "qti-feedback-block",
        "qti-rubric-block",
        "qti-template-block",
        "qti-test-feedback",
    )
)
# Test-level elements of the full QTI 3.0 ASI schema (imsqti_asiv3p0_v1p0.xsd) that
# the item schema leaves out, with their attributes.
_TEST_VOCABULARY = {
    "qti-assessment-item-ref": (
        "category",
        "class",
        "fixed",
        "href",
        "identifier",
        "required",
    ),
    "qti-assessment-section": (
        "class",
        "fixed",
        "identifier",
        "keep-together",
        "required",
        "title",
        "visible",
    ),
    "qti-assessment-section-ref": ("class", "href", "identifier"),
    "qti-assessment-stimulus": (
        "identifier",
        "label",
        "title",
        "tool-name",
        "tool-version",
    ),
    "qti-assessment-test": (
        "class",
        "identifier",
        "title",
        "tool-name",
        "tool-version",
    ),
    "qti-branch-rule": ("target",),
    "qti-exit-test": (),
    "qti-item-session-control": (
        "allow-comment",
        "allow-review",
        "allow-skipping",
        "max-attempts",
        "show-feedback",
        "show-solution",
        "validate-responses",
    ),
    "qti-ordering": ("shuffle",),
    "qti-outcome-condition": (),
    "qti-outcome-else": (),
    "qti-outcome-else-if": (),
    "qti-outcome-if": (),
    "qti-outcome-processing": (),
    "qti-outcome-processing-fragment": (),
    "qti-pre-condition": (),
    "qti-selection": ("select", "with-replacement"),
    "qti-stimulus-body": (),
    "qti-template-default": ("template-identifier",),
    "qti-test-feedback": (
        "access",
        "identifier",
        "outcome-identifier",
        "show-hide",
        "title",
    ),
    "qti-test-part": (
        "class",
        "identifier",
        "navigation-mode",
        "submission-mode",
        "title",
    ),
    "qti-test-variables": (
        "base-type",
        "exclude-category",
        "include-category",
        "section-identifier",
        "variable-identifier",
        "weight-identifier",
    ),
    "qti-time-limits": ("allow-late-submission", "max-time", "min-time"),
    "qti-variable-mapping": ("source-identifier", "target-identifier"),
    "qti-weight": ("identifier", "value"),
}
_TEMPLATE_ATTRIBUTES = ("template", "template-location")
_QTI3_RPTEMPLATES = "https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/"
_QTI2_RPTEMPLATES = re.compile(
    r"^https?://www\.imsglobal\.org/question/qti_v2p[012]/rptemplates/"
)
_QTI2P2_HTML5_NAMESPACE = "http://www.imsglobal.org/xsd/imsqtiv2p2_html5_v1p0"
# 2.2 puts MathML 3 and SSML 1.1 in namespaces the 3.0 schema does not import.
_MOVED_NAMESPACES = {
    "http://www.w3.org/2010/Math/MathML": ("m", "http://www.w3.org/1998/Math/MathML"),
    "http://www.w3.org/2010/10/synthesis": (
        "ssml",
        "http://www.w3.org/2001/10/synthesis",
    ),
}
_RUBRIC_USES = ("instructions", "scoring", "navigation")
# U+200B keeps the line-break opportunity of 2.2's <wbr>, which 3.0 does not declare.
_WORD_BREAK = "\u200b"
_SPELLINGS = {"centrepoint": "centerpoint"}


def _key(name):
    # 3.0 changed acronym case: 2.x durationGTE is 3.0 qti-duration-gte.
    key = name.replace("-", "").lower()
    return _SPELLINGS.get(key, key)


@lru_cache(maxsize=1)
def _renames():
    """``{2.x name key: (3.0 element name, {2.x attribute name key: 3.0 attribute name})}``."""
    vocabulary = {**item_vocabulary(), **_TEST_VOCABULARY}
    renames = {}
    for name, attributes in vocabulary.items():
        source = (
            name[len("qti-") :].replace("-", "") if name.startswith("qti-") else name
        )
        if source != name and source in vocabulary:
            continue
        renames[_key(source)] = (name, {_key(a): a for a in attributes})
    return renames


class QTIConverter:
    """Converts the root of another QTI version to QTI 3.0.

    Handles roots in ``NAMESPACES``; a format identified otherwise (QTI 1.2's
    un-namespaced ``questestinterop``) overrides ``handles``. ``VERSIONS`` names
    the versions it converts.
    """

    NAMESPACES = ()
    VERSIONS = ()

    def handles(self, root):
        return etree.QName(root).namespace in self.NAMESPACES

    def convert(self, root):
        raise NotImplementedError


class QTI2Converter(QTIConverter):
    NAMESPACES = (
        "http://www.imsglobal.org/xsd/imsqti_v2p1",
        "http://www.imsglobal.org/xsd/imsqti_v2p2",
    )
    VERSIONS = ("2.1", "2.2")

    def convert(self, root):
        source = etree.QName(root).namespace
        # Retagging in place keeps the 2.x default namespace, so 3.0 tags would serialize as ns0:.
        nsmap = {prefix: uri for prefix, uri in root.nsmap.items() if uri != source}
        converted = etree.Element(
            root.tag, root.attrib, nsmap={**nsmap, None: QTI3_NAMESPACE}
        )
        converted.text = root.text
        converted.sourceline = root.sourceline
        converted.extend(list(root))
        for wbr in list(converted.iterdescendants(f"{{{source}}}wbr")):
            wbr.tail = _WORD_BREAK + (wbr.tail or "")
            remove_element(wbr)
        for elem in converted.iter(f"{{{source}}}*", f"{{{_QTI2P2_HTML5_NAMESPACE}}}*"):
            self._rename(elem)
        top_nsmap = {}
        for old, (prefix, new) in _MOVED_NAMESPACES.items():
            for elem in converted.iter(f"{{{old}}}*"):
                elem.tag = f"{{{new}}}{etree.QName(elem).localname}"
                top_nsmap[prefix] = new
        for elem in list(converted.iter(*_CONTENT_BODY_PARENTS)):
            body = etree.SubElement(elem, _CONTENT_BODY_TAG)
            body.sourceline = elem.sourceline
            body.text, elem.text = elem.text, None
            body.extend(elem[:-1])
            if elem.tag == _RUBRIC_BLOCK_TAG and elem.get("use") not in _RUBRIC_USES:
                scoring = "scorer" in elem.get("view", "").split()
                elem.set("use", "scoring" if scoring else "instructions")
        etree.cleanup_namespaces(converted, top_nsmap=top_nsmap)
        return converted

    @staticmethod
    def _rename(elem):
        localname = etree.QName(elem).localname
        name, renames = _renames().get(_key(localname), (localname, {}))
        elem.tag = f"{{{QTI3_NAMESPACE}}}{name}"
        attributes = list(elem.attrib.items())
        elem.attrib.clear()
        for key, value in attributes:
            key = renames.get(_key(key), key)
            if key in _TEMPLATE_ATTRIBUTES:
                value = _QTI2_RPTEMPLATES.sub(_QTI3_RPTEMPLATES, value)
            elem.set(key, value)


DEFAULT_CONVERTERS = (QTI2Converter(),)
SUPPORTED_VERSIONS = (
    f"QTI {', '.join(v for c in DEFAULT_CONVERTERS for v in c.VERSIONS)} or 3.0"
)


def read_qti(package_dir, member, tag):
    """Parse ``member`` as a QTI ``<tag>``; return its root element, converted to QTI 3.0.

    Raises ``ValueError`` saying why the file is unusable.
    """
    path = contained_path(package_dir, member)
    if path is None or not os.path.isfile(path):
        raise ValueError("is missing or outside the package")
    try:
        root = parse_qti(path)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"is not well-formed XML: {e.msg}")
    if etree.QName(root).namespace != QTI3_NAMESPACE:
        converter = next((c for c in DEFAULT_CONVERTERS if c.handles(root)), None)
        if converter is None:
            raise ValueError(f"is not {SUPPORTED_VERSIONS}")
        root = converter.convert(root)
    if root.tag != f"{{{QTI3_NAMESPACE}}}{tag}":
        raise ValueError(f"is not a QTI <{tag}>")
    return root
