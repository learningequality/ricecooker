"""Read QTI files, converting other QTI versions to QTI 3.0."""

import os
import re
from functools import lru_cache

from lxml import etree

from ricecooker.utils.imscp import contained_path
from ricecooker.utils.qti.items import _item_schema
from ricecooker.utils.qti.items import _PARSER
from ricecooker.utils.qti.items import QTI3_NAMESPACE

_QTI3_RPTEMPLATES = "https://purl.imsglobal.org/spec/qti/v3p0/rptemplates/"
_QTI2_RPTEMPLATES = re.compile(
    r"^https?://www\.imsglobal\.org/question/qti_v2p[12]/rptemplates/"
)


def _kebab(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name).lower()


@lru_cache(maxsize=None)
def _qti3_tag(qti2_name):
    # The item schema declares no test elements, so they correctly fall through to qti- names.
    _, html = _item_schema()
    name = qti2_name if qti2_name in html else "qti-" + _kebab(qti2_name)
    return f"{{{QTI3_NAMESPACE}}}{name}"


class QTIConverter:
    """Converts the root of another QTI version to QTI 3.0.

    Handles roots in ``NAMESPACES``; a format identified otherwise (QTI 1.2's
    un-namespaced ``questestinterop``) overrides ``handles``. ``VERSIONS`` maps
    the manifest resource-type tokens it converts to their version names.
    """

    NAMESPACES = ()
    VERSIONS = {}

    def handles(self, root):
        return etree.QName(root).namespace in self.NAMESPACES

    def convert(self, root):
        raise NotImplementedError


class QTI2Converter(QTIConverter):
    NAMESPACES = (
        "http://www.imsglobal.org/xsd/imsqti_v2p1",
        "http://www.imsglobal.org/xsd/imsqti_v2p2",
    )
    VERSIONS = {"v2p1": "2.1", "v2p2": "2.2"}

    def convert(self, root):
        source = etree.QName(root).namespace
        # Retagging in place keeps the 2.x default namespace, so 3.0 tags would serialize as ns0:.
        nsmap = {prefix: uri for prefix, uri in root.nsmap.items() if uri != source}
        converted = etree.Element(
            root.tag, root.attrib, nsmap={**nsmap, None: QTI3_NAMESPACE}
        )
        converted.text = root.text
        converted.extend(list(root))
        for elem in converted.iter(f"{{{source}}}*"):
            self._rename(elem)
        etree.cleanup_namespaces(converted)
        return converted

    @staticmethod
    def _rename(elem):
        elem.tag = _qti3_tag(etree.QName(elem).localname)
        # Rebuilt rather than renamed one by one, to keep attribute order.
        attributes = list(elem.attrib.items())
        elem.attrib.clear()
        for key, value in attributes:
            if etree.QName(key).namespace is None:
                key = _kebab(key)
            if key == "template":
                value = _QTI2_RPTEMPLATES.sub(_QTI3_RPTEMPLATES, value)
            elem.set(key, value)


DEFAULT_CONVERTERS = (QTI2Converter(),)
_CONVERTED = {
    token: name for c in DEFAULT_CONVERTERS for token, name in c.VERSIONS.items()
}
QTI_RESOURCE_VERSIONS = (*_CONVERTED, "v3p0")
SUPPORTED_VERSIONS = f"QTI {', '.join(_CONVERTED.values())} or 3.0"


def read_qti(package_dir, member, tag):
    """Parse ``member`` as a QTI ``<tag>``; return its root element, converted to QTI 3.0.

    Raises ``ValueError`` saying why the file is unusable.
    """
    path = contained_path(package_dir, member)
    if path is None or not os.path.isfile(path):
        raise ValueError("is missing or outside the package")
    try:
        root = etree.parse(path, _PARSER).getroot()
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
