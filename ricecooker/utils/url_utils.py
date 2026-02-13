"""
Shared URL extraction and rewriting utilities for archive processing.

These functions operate on content strings (HTML, CSS, JSON) — no HTTP,
no filesystem, no platform-specific paths. They can be used by both
ricecooker's pipeline and Studio's upload processing.

Supersedes issue #303 by making URL detection/rewriting independently
unit-testable.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


@dataclass
class ExtractedURL:
    """A URL reference found in archive content."""

    url: str  # The URL as found in the source
    source_file: str  # Which file this was found in (for archive context)
    context: str  # 'html_attr', 'css_url', 'css_import', 'h5p_json', 'html_srcset'
    tag: Optional[str] = None  # e.g. 'img', 'link', 'script'
    attr: Optional[str] = None  # e.g. 'src', 'href'


# Regex patterns for CSS URL extraction
# Matches url('...'), url("..."), and url(...)
_CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")
# Matches @import '...' and @import "..." (bare string form, not url() form)
_CSS_IMPORT_RE = re.compile(r"@import\s+['\"]([^'\"]+)['\"]")


def is_external_url(url):
    """
    Classify a URL as external (http/https with a netloc) vs internal
    (relative path, data: URI, fragment-only, etc.).
    """
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def derive_local_filename(url):
    """
    Derive a deterministic local filename from an external URL.

    Example:
        'https://fonts.example.com/font.woff2'
        -> '_external/fonts.example.com/font.woff2'
    """
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    # Strip path traversal segments to prevent writing outside the archive
    parts = path.split("/")
    parts = [p for p in parts if p != ".."]
    path = "/".join(parts)
    if parsed.query:
        path = path + "?" + parsed.query
    return os.path.join("_external", parsed.netloc, path)


def extract_urls_from_css(css_content, source_file=""):
    """
    Extract all external URL references from CSS content.

    Finds URLs in:
    - url('...'), url("..."), url(...)
    - @import '...' and @import "..." (bare string form)

    Skips data: URIs and relative URLs.
    Returns list of ExtractedURL instances.
    """
    results = []
    seen = set()

    # First pass: url() references
    for match in _CSS_URL_RE.finditer(css_content):
        url = match.group(1).strip()
        if url and is_external_url(url) and url not in seen:
            seen.add(url)
            results.append(
                ExtractedURL(url=url, source_file=source_file, context="css_url")
            )

    # Second pass: bare @import strings (not url() form)
    for match in _CSS_IMPORT_RE.finditer(css_content):
        url = match.group(1).strip()
        if url and is_external_url(url) and url not in seen:
            seen.add(url)
            results.append(
                ExtractedURL(url=url, source_file=source_file, context="css_import")
            )

    return results


def _parse_srcset(srcset_value):
    """Parse an HTML srcset attribute value into a list of URLs."""
    urls = []
    for entry in srcset_value.split(","):
        entry = entry.strip()
        if entry:
            # srcset entries are "url descriptor" e.g. "img.jpg 300w"
            parts = entry.split()
            if parts:
                urls.append(parts[0])
    return urls


def extract_urls_from_html(html_content, source_file=""):
    """
    Extract all external URL references from HTML content.

    Finds URLs in:
    - img[src], script[src], source[src]
    - img[srcset], source[srcset]
    - link[rel=stylesheet][href]
    - inline style attributes with url()
    - <style> blocks

    Skips data: URIs and relative URLs.
    Returns list of ExtractedURL instances.
    """
    if not html_content or not html_content.strip():
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    results = []
    seen = set()

    # img[src], script[src], source[src]
    for tag_name in ("img", "script", "source"):
        for node in soup.find_all(tag_name, src=True):
            url = node["src"]
            if is_external_url(url) and url not in seen:
                seen.add(url)
                results.append(
                    ExtractedURL(
                        url=url,
                        source_file=source_file,
                        context="html_attr",
                        tag=tag_name,
                        attr="src",
                    )
                )

    # img[srcset], source[srcset]
    for tag_name in ("img", "source"):
        for node in soup.find_all(tag_name, srcset=True):
            for url in _parse_srcset(node["srcset"]):
                if is_external_url(url) and url not in seen:
                    seen.add(url)
                    results.append(
                        ExtractedURL(
                            url=url,
                            source_file=source_file,
                            context="html_srcset",
                            tag=tag_name,
                            attr="srcset",
                        )
                    )

    # link[rel=stylesheet][href] — use "rel" in node.attrs (PR #636 fix)
    for node in soup.find_all("link", href=True):
        if "rel" in node.attrs and "stylesheet" in node.get("rel", []):
            url = node["href"]
            if is_external_url(url) and url not in seen:
                seen.add(url)
                results.append(
                    ExtractedURL(
                        url=url,
                        source_file=source_file,
                        context="html_attr",
                        tag="link",
                        attr="href",
                    )
                )

    # Inline style attributes with url()
    for node in soup.find_all(style=True):
        style_val = node.get("style", "")
        for extracted in extract_urls_from_css(style_val, source_file):
            if extracted.url not in seen:
                seen.add(extracted.url)
                results.append(extracted)

    # <style> blocks
    for style_node in soup.find_all("style"):
        if style_node.string:
            for extracted in extract_urls_from_css(style_node.string, source_file):
                if extracted.url not in seen:
                    seen.add(extracted.url)
                    results.append(extracted)

    return results


def extract_urls_from_h5p_json(json_content, source_file=""):
    """
    Extract external URL references from H5P JSON content.

    Walks the JSON tree recursively, finding any "path" keys whose values
    are external URLs (start with http:// or https://).
    """
    try:
        data = json.loads(json_content)
    except (json.JSONDecodeError, TypeError):
        return []

    results = []

    def _walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "path" and isinstance(value, str) and is_external_url(value):
                    results.append(
                        ExtractedURL(
                            url=value, source_file=source_file, context="h5p_json"
                        )
                    )
                else:
                    _walk(value)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return results


def rewrite_urls_in_css(css_content, url_map):
    """
    Rewrite URL references in CSS content using the provided mapping.

    Handles both url() and @import bare string forms.
    URLs not in the map are left unchanged.
    """

    def _repl_url(match):
        original = match.group(0)
        url = match.group(1).strip()
        if url in url_map:
            return "url('{}')".format(url_map[url])
        return original

    def _repl_import(match):
        original = match.group(0)
        url = match.group(1).strip()
        if url in url_map:
            return "@import '{}'".format(url_map[url])
        return original

    result = _CSS_URL_RE.sub(_repl_url, css_content)
    result = _CSS_IMPORT_RE.sub(_repl_import, result)
    return result


def rewrite_urls_in_html(html_content, url_map):
    """
    Rewrite URL references in HTML content using the provided mapping.

    Handles the same selectors as extract_urls_from_html:
    img/script/source src, img/source srcset, link[stylesheet] href,
    inline styles, and <style> blocks.

    URLs not in the map are left unchanged.
    """
    if not html_content or not html_content.strip():
        return html_content

    soup = BeautifulSoup(html_content, "html.parser")

    # img[src], script[src], source[src]
    for tag_name in ("img", "script", "source"):
        for node in soup.find_all(tag_name, src=True):
            url = node["src"]
            if url in url_map:
                node["src"] = url_map[url]

    # img[srcset], source[srcset]
    for tag_name in ("img", "source"):
        for node in soup.find_all(tag_name, srcset=True):
            entries = []
            for entry in node["srcset"].split(","):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split()
                url = parts[0]
                if url in url_map:
                    parts[0] = url_map[url]
                entries.append(" ".join(parts))
            node["srcset"] = ", ".join(entries)

    # link[rel=stylesheet][href]
    for node in soup.find_all("link", href=True):
        if "rel" in node.attrs and "stylesheet" in node.get("rel", []):
            url = node["href"]
            if url in url_map:
                node["href"] = url_map[url]

    # Inline style attributes
    for node in soup.find_all(style=True):
        style_val = node.get("style", "")
        node["style"] = rewrite_urls_in_css(style_val, url_map)

    # <style> blocks
    for style_node in soup.find_all("style"):
        if style_node.string:
            style_node.string = rewrite_urls_in_css(style_node.string, url_map)

    return str(soup)


def rewrite_urls_in_h5p_json(json_content, url_map):
    """
    Rewrite "path" values in H5P JSON content using the provided mapping.

    Walks the JSON tree recursively, replacing matching "path" values.
    URLs not in the map are left unchanged.
    """
    try:
        data = json.loads(json_content)
    except (json.JSONDecodeError, TypeError):
        return json_content

    def _walk(obj):
        if isinstance(obj, dict):
            for key in obj:
                if key == "path" and isinstance(obj[key], str) and obj[key] in url_map:
                    obj[key] = url_map[obj[key]]
                else:
                    _walk(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return json.dumps(data)
