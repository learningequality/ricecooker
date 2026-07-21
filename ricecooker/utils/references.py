"""Detect and rewrite resource references in HTML/CSS strings.

Pure functions over strings (no HTTP/filesystem), so they unit test directly
(supersedes #303). Each file type is a :class:`ReferenceMapper` modeled on
kolibri-zip's ``Mapper``; ``map`` applies ``fn(url) -> url`` to every reference,
``extract``/``rewrite`` wrap it. HTML rewriting is surgical — only reference
spans are spliced, so a re-serialization pass cannot corrupt third-party
archives. Standard library only.
"""

import re
from html.parser import HTMLParser
from typing import Callable
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple
from urllib.parse import urlparse

CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")

# @import can take a bare string instead of a url(); that form is caught here,
# the url() form by CSS_URL_RE above.
CSS_IMPORT_RE = re.compile(r"@import\s*['\"](.*?)['\"]")


def is_external_url(url: str) -> bool:
    """True for absolute http(s) URLs and protocol-relative ``//host/...`` refs.

    Relative paths, ``data:``/``blob:`` URIs, bare fragments and empty strings
    are all internal (or non-fetchable) and return False.
    """
    if url.startswith("//"):
        return True
    return urlparse(url).scheme in ("http", "https")


def _map_css_urls(css: str, fn: Callable[[str], str]) -> Tuple[str, List[str]]:
    """Walk every ``url(...)`` and bare-string ``@import`` reference in ``css``.

    Applies ``fn`` to each captured URL, substitutes the result back in place of
    the original (preserving the surrounding wrapper and quotes), and returns
    the rewritten CSS plus the original URLs in order of appearance.
    """
    matches = []
    for regex in (CSS_URL_RE, CSS_IMPORT_RE):
        matches.extend(regex.finditer(css))
    matches.sort(key=lambda m: m.start(1))
    urls = [m.group(1) for m in matches]
    # Splice the mapped URL over each captured span, leaving the url()/@import
    # wrapper and quotes untouched. Shares _apply_edits with the HTML rewriter.
    edits = [(*m.span(1), fn(m.group(1))) for m in matches]
    return _apply_edits(css, edits), urls


def _is_stylesheet_attrs(attrs: Dict[str, str]) -> bool:
    """True for a ``<link>`` that references a stylesheet.

    ``rel`` is space-separated, so test membership after splitting (#636). Also
    treat a link as a stylesheet when its href path ends ``.css``.
    """
    if "stylesheet" in attrs.get("rel", "").split():
        return True
    return urlparse(attrs.get("href", "")).path.endswith(".css")


def _map_srcset(srcset: str, fn: Callable[[str], str]) -> Tuple[str, List[str]]:
    """Apply ``fn`` to each url in a ``srcset``, preserving descriptors."""
    urls = []
    rewritten = []
    for source in srcset.split(","):
        parts = source.split()
        if not parts:
            continue
        urls.append(parts[0])
        parts[0] = fn(parts[0])
        rewritten.append(" ".join(parts))
    return ", ".join(rewritten), urls


def _compile_attr_value_re(attr: str) -> "re.Pattern":
    # Capture the double-quoted / single-quoted / unquoted value forms. The
    # lookbehind keeps ``src`` from matching inside ``data-src`` (or ``href``
    # inside ``xlink:href``).
    return re.compile(
        r"(?<![\w:-])"
        + re.escape(attr)
        + r"""\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""",
        re.IGNORECASE,
    )


# Only these four attributes are ever located (see _HTMLReferenceRewriter._handle_tag).
_ATTR_VALUE_RES = {
    attr: _compile_attr_value_re(attr) for attr in ("src", "href", "srcset", "style")
}


def _attr_value_span(raw_tag: str, attr: str):
    """Return ``(start, end, value)`` of ``attr``'s value in ``raw_tag`` or None."""
    match = _ATTR_VALUE_RES[attr].search(raw_tag)
    if match is None:
        return None
    for group in (1, 2, 3):
        if match.group(group) is not None:
            return match.start(group), match.end(group), match.group(group)
    return None


class _SurgicalHTMLParser(HTMLParser):
    """Base for parsers that record ``(start, end, replacement)`` edits against the
    original HTML with a forward-only cursor, so unmatched bytes survive verbatim.
    """

    def __init__(self, html: str, convert_charrefs: bool = True):
        super().__init__(convert_charrefs=convert_charrefs)
        self._html = html
        self._cursor = 0
        self.edits: List[Tuple[int, int, str]] = []

    def _tag_offset(self, raw_tag: str) -> int:
        """Absolute offset of ``raw_tag``, advancing a forward-only cursor.

        HTMLParser feeds tokens in document order, so a monotonic search from the
        previous match locates each token — including repeated identical tags —
        with no column arithmetic or CR/LF fixups.
        """
        offset = self._html.find(raw_tag, self._cursor)
        if offset >= 0:
            self._cursor = offset + len(raw_tag)
        return offset


class _HTMLReferenceRewriter(_SurgicalHTMLParser):
    """Collects surgical rewrite edits for the resource references in an HTML doc.

    Detects ``src`` on any element, stylesheet ``link[href]``, ``srcset``, inline
    ``style`` and ``<style>`` block text. Navigation references (``<a href>``,
    ``<iframe src>``) are excluded: they are page links, not offline resources.
    """

    def __init__(self, html: str, fn: Callable[[str], str]):
        super().__init__(html, convert_charrefs=False)
        self._fn = fn
        self._style_depth = 0
        self.urls: List[str] = []

    def _record(self, attr: str, kind: str, raw_tag: str, base: int):
        span = _attr_value_span(raw_tag, attr)
        if span is None:
            return
        rel_start, rel_end, value = span
        if kind == "url":
            self.urls.append(value)
            replacement = self._fn(value)
        elif kind == "srcset":
            replacement, urls = _map_srcset(value, self._fn)
            self.urls.extend(urls)
        else:  # inline css
            replacement, urls = _map_css_urls(value, self._fn)
            self.urls.extend(urls)
        self.edits.append((base + rel_start, base + rel_end, replacement))

    def _handle_tag(self, tag: str, attrs):
        raw_tag = self.get_starttag_text()
        if raw_tag is None:
            return
        base = self._tag_offset(raw_tag)
        if base < 0:
            return
        attr_map = {name.lower(): (value or "") for name, value in attrs}
        if "src" in attr_map:
            self._record("src", "url", raw_tag, base)
        if tag == "link" and _is_stylesheet_attrs(attr_map):
            self._record("href", "url", raw_tag, base)
        if "srcset" in attr_map:
            self._record("srcset", "srcset", raw_tag, base)
        if "style" in attr_map:
            self._record("style", "css", raw_tag, base)

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self._style_depth += 1
        self._handle_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle_tag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "style" and self._style_depth > 0:
            self._style_depth -= 1

    def handle_data(self, data):
        if self._style_depth <= 0 or not data.strip():
            return
        start = self._html.find(data, self._cursor)
        if start < 0:
            return
        self._cursor = start + len(data)
        replacement, urls = _map_css_urls(data, self._fn)
        self.urls.extend(urls)
        self.edits.append((start, start + len(data), replacement))


def _apply_edits(text: str, edits: List[Tuple[int, int, str]]) -> str:
    """Splice ``(start, end, replacement)`` edits into ``text`` in one pass."""
    parts = []
    last = 0
    for start, end, replacement in sorted(edits):
        if start < last:
            continue  # defensively skip any overlapping span
        parts.append(text[last:start])
        parts.append(replacement)
        last = end
    parts.append(text[last:])
    return "".join(parts)


def _map_html_urls(html: str, fn: Callable[[str], str]) -> Tuple[str, List[str]]:
    """Walk every resource reference in ``html``, applying ``fn`` to each.

    Detects ``src`` on any element, stylesheet ``link[href]``, ``srcset``, inline
    ``style`` attributes and ``<style>`` block text. Rewriting is surgical: only
    the matched reference spans are replaced, so the rest of the document
    (whitespace, inline scripts, tag casing) is byte-for-byte preserved.
    """
    rewriter = _HTMLReferenceRewriter(html, fn)
    rewriter.feed(html)
    rewriter.close()
    return _apply_edits(html, rewriter.edits), rewriter.urls


def _filter_css_declarations(css: str, allowed: Set[str]) -> Tuple[str, List[str]]:
    """Keep only declarations whose property is in ``allowed``.

    Returns ``(kept_css, dropped_property_names)``. Splits naively on ``;``/``:``,
    which is correct for the v1 allowlist (``text-align``/``color``/
    ``background-color`` values never contain ``;`` or ``:``).
    """
    kept, dropped = [], []
    for decl in css.split(";"):
        if not decl.strip():
            continue
        prop = decl.split(":", 1)[0].strip().lower()
        if prop in allowed:
            kept.append(decl.strip())
        else:
            dropped.append(prop)
    return "; ".join(kept), dropped


_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.IGNORECASE | re.DOTALL)


class _HTMLStyleSanitizer(_SurgicalHTMLParser):
    """Records surgical edits that allowlist-filter inline ``style=`` attributes.

    ``<style>`` blocks are stripped separately by a regex pass in
    :func:`sanitize_style_css` before parsing.
    """

    def __init__(self, html: str, allowed_properties: Set[str]):
        super().__init__(html)
        self._allowed = allowed_properties
        self.removed: List[str] = []

    def _handle_tag(self):
        raw_tag = self.get_starttag_text()
        if raw_tag is None:
            return
        base = self._tag_offset(raw_tag)
        # _attr_value_span returns None when the tag has no style= attribute.
        span = _attr_value_span(raw_tag, "style")
        if base < 0 or span is None:
            return
        rel_start, rel_end, value = span
        kept, dropped = _filter_css_declarations(value, self._allowed)
        if dropped:
            self.edits.append((base + rel_start, base + rel_end, kept))
            self.removed.extend(f"style property '{p}'" for p in dropped)

    def handle_starttag(self, tag, attrs):
        self._handle_tag()

    def handle_startendtag(self, tag, attrs):
        self._handle_tag()


def sanitize_style_css(
    html: str, allowed_properties: Set[str]
) -> Tuple[str, List[str]]:
    """Strip ``<style>`` blocks and allowlist-filter inline ``style=`` attributes.

    Returns ``(html, removed)`` — descriptors of what was stripped, empty if unchanged.
    """
    html, n_blocks = _STYLE_BLOCK_RE.subn("", html)
    removed = ["<style> block"] * n_blocks
    parser = _HTMLStyleSanitizer(html, allowed_properties)
    parser.feed(html)
    parser.close()
    return _apply_edits(html, parser.edits), removed + parser.removed


# An IE conditional comment can wrap a pandoc-injected html5shiv <script>; strip
# both so a KPUB stays script-free regardless of which pandoc template generated it.
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_IE_CONDITIONAL_COMMENT_RE = re.compile(
    r"<!--\[if[^\]]*\]>.*?<!\[endif\]-->", re.IGNORECASE | re.DOTALL
)


def strip_scripts(html: str) -> Tuple[str, List[str]]:
    """Remove ``<script>`` elements and IE conditional comments from ``html``.

    Returns ``(html, removed)`` — descriptors of what was stripped, empty if unchanged.
    """
    # Strip conditional comments first so the script they wrap is gone before the pass below.
    html, n_comments = _IE_CONDITIONAL_COMMENT_RE.subn("", html)
    html, n_scripts = _SCRIPT_RE.subn("", html)
    removed = ["IE conditional comment"] * n_comments + ["<script> block"] * n_scripts
    return html, removed


class ReferenceMapper:
    """Detects and rewrites external resource references for one file type.

    Modeled on kolibri-zip's ``Mapper``. A subclass implements :meth:`map`, which
    applies ``fn(url) -> url`` to every reference and returns
    ``(rewritten_content, urls)``; :meth:`extract` and :meth:`rewrite` wrap it.
    The default :meth:`handles` matches by ``EXTENSIONS``; formats identified some
    other way (e.g. a fixed archive path) override it.
    """

    EXTENSIONS: Tuple[str, ...] = ()

    def handles(self, path: str) -> bool:
        return bool(self.EXTENSIONS) and path.lower().endswith(self.EXTENSIONS)

    def map(self, content: str, fn: Callable[[str], str]) -> Tuple[str, List[str]]:
        """Apply ``fn`` to every reference; return ``(rewritten, urls)``."""
        raise NotImplementedError

    def extract(self, content: str) -> List[str]:
        return self.map(content, lambda u: u)[1]

    def rewrite(self, content: str, mapping: Dict[str, str]) -> str:
        return self.map(content, lambda u: mapping.get(u, u))[0]


class HTMLMapper(ReferenceMapper):
    """References in HTML/XML: ``src``/``href``/``srcset``, inline and block CSS."""

    EXTENSIONS = (".html", ".htm", ".xhtml", ".xml")

    def map(self, content: str, fn: Callable[[str], str]) -> Tuple[str, List[str]]:
        return _map_html_urls(content, fn)


class CSSMapper(ReferenceMapper):
    """References in CSS: ``url(...)`` and bare-string ``@import``."""

    EXTENSIONS = (".css",)

    def map(self, content: str, fn: Callable[[str], str]) -> Tuple[str, List[str]]:
        return _map_css_urls(content, fn)


# Generic web defaults, mirroring kolibri-zip's ``defaultFilePathMappers``. A
# format with its own reference style (e.g. H5P) extends this with its own mapper.
DEFAULT_MAPPERS = (HTMLMapper(), CSSMapper())
