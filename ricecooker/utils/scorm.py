"""Conservative classifiers for SCORM/IMSCP webcontent resources.

LMS-communication boilerplate is discounted first, or every SCO looks interactive.
Pure functions over already-read HTML and member names; the caller does the I/O.
"""

import re

from bs4 import BeautifulSoup
from le_utils.constants import file_formats

from ricecooker.utils.paths import extract_path_ext
from ricecooker.utils.references import _attr_value_span
from ricecooker.utils.references import SCRIPT_TAG_RE

# Script ``src``/name substrings identifying SCORM API boilerplate, matched
# case-insensitively. These wire a SCO up to the LMS and carry no content.
SCORM_BOILERPLATE_SCRIPT_HINTS = frozenset(
    {
        "pipwerks",
        "scorm_api_wrapper",
        "scofunctions",
        "scormapi",
        "scorm_handlers",
        "apiwrapper",
        "scormfunctions",
    }
)

# SCORM 1.2 (``LMS*``, ``doLMS*``) and 2004 (``API_1484_11.*``) LMS API calls.
SCORM_API_CALL_RE = re.compile(
    r"\b(?:do)?LMS\w+\s*\(|\bAPI(?:_1484_11)?\.\w+\s*\(|\bpipwerks\b"
)

# Page access marks an inline script as content, even if it also talks to the LMS.
_CONTENT_SCRIPT_RE = re.compile(
    r"\bdocument\.|\.innerHTML\b|\$\(|\bjQuery\b|\balert\s*\("
)

# Recording a grade is assessment meaning whatever else the script does.
SCORM_SCORE_RE = re.compile(r"cmi\.core\.score|cmi\.score", re.IGNORECASE)

# Content SCOs report completion too; only a pass/fail status is a grade.
SCORM_PASS_FAIL_STATUS_RE = re.compile(
    r"cmi\.(?:core\.lesson_status|success_status).*?[\"'](?:passed|failed)[\"']",
    re.IGNORECASE | re.DOTALL,
)

# HotPotatoes quiz engine globals; their presence means the page IS an exercise.
_HOTPOTATOES_GLOBALS_RE = re.compile(r"JQuiz|JCloze|JMatch|JMix|JCross", re.IGNORECASE)
# The generator's <meta content="... Hot Potatoes ..."> stamp.
_HOTPOTATOES_META_RE = re.compile(
    r"<meta\b[^>]*\bcontent\s*=\s*[\"'][^\"']*hot\s+potatoes", re.IGNORECASE
)

_MEDIA_TAGS = ("video", "audio", "img", "embed", "iframe")

# Images are absent deliberately: Kolibri has no image kind, so a page wrapping
# one picture stays the (KPUB-qualifying) article it already is.
MEDIA_EXTENSIONS = {
    file_formats.MP4,
    file_formats.WEBM,
    file_formats.MP3,
    file_formats.PDF,
}


def _script_src(attrs):
    span = _attr_value_span(attrs, "src")
    return span[2] if span else None


def _is_boilerplate_src(src):
    lower = src.lower()
    return any(hint in lower for hint in SCORM_BOILERPLATE_SCRIPT_HINTS)


def _is_boilerplate_script(attrs, body):
    """True for a known wrapper file, or an inline block that only talks to the LMS."""
    src = _script_src(attrs)
    if src is not None:
        return _is_boilerplate_src(src)
    return bool(SCORM_API_CALL_RE.search(body)) and not _CONTENT_SCRIPT_RE.search(body)


def strip_scorm_boilerplate(html):
    """Return ``html`` with SCORM API boilerplate ``<script>`` tags removed.

    Wrapper ``src=`` tags and inline plumbing blocks go; content scripts stay.
    """

    def replace(match):
        if _is_boilerplate_script(match.group(1), match.group(2)):
            return ""
        return match.group(0)

    return SCRIPT_TAG_RE.sub(replace, html)


def boilerplate_script_members(names):
    """The ``.js`` members of ``names`` that are SCORM API wrappers."""
    return [
        name
        for name in names
        if name.lower().endswith(".js") and _is_boilerplate_src(name)
    ]


def has_assessment_semantics(index_html, mastery_score=None):
    """True when a webcontent resource carries assessment/score/tracking meaning.

    Any one signal is enough: a HotPotatoes-generated page, an
    ``adlcp:masteryscore``, or an inline script writing a score or pass/fail status.
    """
    if _HOTPOTATOES_META_RE.search(index_html):
        return True
    if _HOTPOTATOES_GLOBALS_RE.search(index_html):
        return True
    if mastery_score:
        return True
    # Only the index's own inline scripts are inspected — wrapper .js members
    # reference cmi.* as API surface, not as a graded resource's own behaviour.
    for match in SCRIPT_TAG_RE.finditer(index_html):
        attrs, body = match.group(1), match.group(2)
        if _script_src(attrs) is not None:
            continue
        if SCORM_SCORE_RE.search(body) or SCORM_PASS_FAIL_STATUS_RE.search(body):
            return True
    return False


def _references(tag, media_name):
    """True when ``tag`` (or a nested ``<source>``) points at ``media_name``."""
    return any(
        (t.get("src") or "").split("/")[-1] == media_name
        for t in [tag, *tag.find_all("source")]
    )


def single_media_member(index_html, index_file, files):
    """Return the archive-member path if the resource reduces to one media file.

    Qualifies only when, excluding the index and discounted boilerplate, exactly
    one member remains, it has a media extension, and the index body's only
    meaningful element references it. Any ambiguity returns ``None``.
    """
    index_name = index_file.split("/")[-1]
    boilerplate = set(boilerplate_script_members(files))
    remaining = [
        member
        for member in files
        if member.split("/")[-1] != index_name and member not in boilerplate
    ]

    if len(remaining) != 1:
        return None
    media = remaining[0]
    try:
        if extract_path_ext(media) not in MEDIA_EXTENSIONS:
            return None
    except ValueError:  # an extension-less member is not media
        return None

    body = BeautifulSoup(index_html, "html5lib").find("body")
    if body is None:
        return None
    media_tags = body.find_all(_MEDIA_TAGS)
    if len(media_tags) != 1 or not _references(media_tags[0], media.split("/")[-1]):
        return None
    # Prose or controls alongside the media element make this a richer article,
    # which stays an HTML5/KPUB zip rather than collapsing to a bare media node.
    if body.get_text(strip=True):
        return None
    if body.find_all(["a", "form", "input", "button", "select", "textarea"]):
        return None
    return media
