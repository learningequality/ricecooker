"""
Archive external reference processor.

Opens an archive (ZIP/H5P), scans text-based files for external URL references,
downloads those resources, bundles them into the archive, and rewrites references
to point to local copies.
"""

import logging
import os
import tempfile
import zipfile

from ricecooker.utils.downloader import make_request
from ricecooker.utils.url_utils import derive_local_filename
from ricecooker.utils.url_utils import extract_urls_from_css
from ricecooker.utils.url_utils import extract_urls_from_h5p_json
from ricecooker.utils.url_utils import extract_urls_from_html
from ricecooker.utils.url_utils import rewrite_urls_in_css
from ricecooker.utils.url_utils import rewrite_urls_in_h5p_json
from ricecooker.utils.url_utils import rewrite_urls_in_html

logger = logging.getLogger(__name__)

# Map file extensions to content type for selecting the right extractor/rewriter
_TEXT_EXTENSIONS = {
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".xml": "html",
    ".css": "css",
    ".json": "json",
}


def _is_h5p_content_json(filepath):
    """Check if a JSON file is an H5P content.json that should be scanned."""
    normalized = filepath.replace("\\", "/")
    return normalized == "content/content.json" or normalized.endswith(
        "/content/content.json"
    )


def _detect_content_type(filepath):
    """Detect the content type of a file based on its extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        if _is_h5p_content_json(filepath):
            return "json"
        return None  # Skip non-H5P JSON files
    return _TEXT_EXTENSIONS.get(ext)


def _compute_relative_path(from_file, to_file):
    """Compute relative path from one file to another within the archive."""
    from_dir = os.path.dirname(from_file)
    return os.path.relpath(to_file, from_dir).replace("\\", "/")


def _is_blacklisted(url, blacklist):
    """Check if a URL matches any blacklist substring."""
    if not blacklist:
        return False
    return any(pattern in url for pattern in blacklist)


def _download_external_url(url, dest_dir, local_path):
    """
    Download a single external URL to the destination directory.

    Returns True on success, False on failure.
    """
    full_path = os.path.join(dest_dir, local_path)
    # Guard against path traversal — resolved path must stay within dest_dir
    resolved = os.path.realpath(full_path)
    if not resolved.startswith(os.path.realpath(dest_dir) + os.sep):
        logger.warning("Path traversal detected for %s, skipping download", url)
        return False
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    try:
        response = make_request(url)
        if response is None or response.status_code != 200:
            logger.warning("Failed to download %s (no response or non-200)", url)
            return False
        with open(full_path, "wb") as f:
            f.write(response.content)
        return True
    except (OSError, IOError, ValueError):
        logger.warning("Error downloading %s", url, exc_info=True)
        return False


def _extract_urls_from_file(full_path, rel_path, content_type):
    """Extract external URLs from a single file. Returns list or None on error."""
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError):
        logger.warning("Could not read %s as text, skipping", rel_path)
        return None

    extractors = {
        "html": extract_urls_from_html,
        "css": extract_urls_from_css,
        "json": extract_urls_from_h5p_json,
    }
    extractor = extractors.get(content_type)
    if extractor is None:
        return None
    return extractor(content, rel_path)


def _scan_archive_for_urls(temp_dir, url_blacklist):
    """Scan all text files in an extracted archive for external URLs."""
    all_urls = {}  # url -> derive_local_filename result
    file_urls = {}  # filepath -> list of extracted URLs

    for root, _dirs, filenames in os.walk(temp_dir):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, temp_dir)
            content_type = _detect_content_type(rel_path)
            if content_type is None:
                continue

            extracted = _extract_urls_from_file(full_path, rel_path, content_type)
            if extracted is None:
                continue

            external = [
                e for e in extracted if not _is_blacklisted(e.url, url_blacklist)
            ]
            if external:
                file_urls[rel_path] = external
                for e in external:
                    if e.url not in all_urls:
                        all_urls[e.url] = derive_local_filename(e.url)

    return all_urls, file_urls


def _download_all_urls(temp_dir, all_urls, url_blacklist):
    """Download all external URLs, including recursive CSS references."""
    successful_downloads = set()
    visited_urls = set()

    for url, local_path in list(all_urls.items()):
        if url in visited_urls:
            continue
        visited_urls.add(url)

        if _download_external_url(url, temp_dir, local_path):
            successful_downloads.add(url)
            if local_path.endswith(".css") or "css" in local_path.split("?")[0]:
                _process_downloaded_css(
                    temp_dir,
                    local_path,
                    all_urls,
                    successful_downloads,
                    visited_urls,
                    url_blacklist,
                )

    return successful_downloads


def _rewrite_file(temp_dir, rel_path, url_map):
    """Rewrite URL references in a single file."""
    full_path = os.path.join(temp_dir, rel_path)
    content_type = _detect_content_type(rel_path)

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    rewriters = {
        "html": rewrite_urls_in_html,
        "css": rewrite_urls_in_css,
        "json": rewrite_urls_in_h5p_json,
    }
    rewriter = rewriters.get(content_type)
    if rewriter:
        content = rewriter(content, url_map)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)


def download_and_rewrite_external_refs(archive_path, url_blacklist=None):
    """
    Process an archive to download external URL references and rewrite them
    to local paths.

    Args:
        archive_path: Path to the archive file (ZIP or H5P)
        url_blacklist: Optional list of URL substrings to skip

    Returns:
        Path to a temporary directory containing the processed archive contents.
        The caller is responsible for cleaning up this directory.
    """
    temp_dir = tempfile.mkdtemp(prefix="ricecooker_archive_")

    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(temp_dir)

    all_urls, file_urls = _scan_archive_for_urls(temp_dir, url_blacklist)

    if not all_urls:
        return temp_dir

    successful_downloads = _download_all_urls(temp_dir, all_urls, url_blacklist)

    for rel_path, extracted_list in file_urls.items():
        url_map = {}
        for e in extracted_list:
            if e.url in successful_downloads:
                local_path = all_urls[e.url]
                url_map[e.url] = _compute_relative_path(rel_path, local_path)
        if url_map:
            _rewrite_file(temp_dir, rel_path, url_map)

    return temp_dir


def _process_downloaded_css(
    temp_dir,
    css_local_path,
    all_urls,
    successful_downloads,
    visited_urls,
    url_blacklist,
):
    """Scan a downloaded CSS file for additional external references and download them."""
    full_path = os.path.join(temp_dir, css_local_path)
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            css_content = f.read()
    except (UnicodeDecodeError, OSError):
        return

    extracted = extract_urls_from_css(css_content, css_local_path)
    external = [e for e in extracted if not _is_blacklisted(e.url, url_blacklist)]

    if not external:
        return

    # Download newly found external URLs
    css_url_map = {}
    for e in external:
        if e.url in visited_urls:
            continue
        visited_urls.add(e.url)

        local_path = derive_local_filename(e.url)
        all_urls[e.url] = local_path

        if _download_external_url(e.url, temp_dir, local_path):
            successful_downloads.add(e.url)
            css_url_map[e.url] = _compute_relative_path(css_local_path, local_path)

    # Also build map for any already-downloaded URLs referenced from this CSS
    for e in external:
        if e.url in successful_downloads and e.url not in css_url_map:
            local_path = all_urls[e.url]
            css_url_map[e.url] = _compute_relative_path(css_local_path, local_path)

    if css_url_map:
        rewritten = rewrite_urls_in_css(css_content, css_url_map)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(rewritten)
