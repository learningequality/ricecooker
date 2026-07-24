"""Conservative classifiers for SCORM/IMSCP webcontent resources.

SCORM buries real content under LMS-communication boilerplate (``pipwerks``
wrappers, ``LMSInitialize``/``SetValue`` calls), so that boilerplate is
discounted first — otherwise every SCO looks interactive. Pure functions over
already-read HTML strings and member names; the caller does the zip I/O.
"""

import re

from bs4 import BeautifulSoup
from le_utils.constants import file_formats

# Script ``src``/name substrings that identify SCORM API boilerplate, matched
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

# SCORM 1.2 / 2004 LMS API calls. An inline script that only makes these is
# boilerplate; one that also writes a score/status carries assessment meaning.
SCORM_API_CALL_RE = re.compile(
    r"\b(LMSInitialize|LMSFinish|LMSGetValue|LMSSetValue|LMSCommit|"
    r"Initialize|Terminate|Commit|GetValue|SetValue)\b"
)

# Data-model elements that only appear when a resource records a grade/progress.
SCORM_SCORE_RE = re.compile(
    r"cmi\.core\.score|cmi\.score|cmi\.core\.lesson_status", re.IGNORECASE
)

# HotPotatoes quiz engine globals. Their presence means the page IS an exercise.
HOTPOTATOES_GLOBALS = ("JQuiz", "JCloze", "JMatch", "JMix", "JCross")

_MEDIA_TAGS = ("video", "audio", "img", "embed", "iframe")

MEDIA_EXTENSIONS = {
    file_formats.MP4,
    file_formats.WEBM,
    file_formats.MP3,
    file_formats.PDF,
    file_formats.PNG,
    file_formats.JPG,
    file_formats.JPEG,
    file_formats.GIF,
}

# One ``<script ...>...</script>`` element; group 1 = attributes, group 2 = body.
_SCRIPT_TAG_RE = re.compile(
    r"<script\b([^>]*)>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL
)
_SRC_ATTR_RE = re.compile(r"""src\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)


def _script_src(attrs):
    match = _SRC_ATTR_RE.search(attrs)
    return match.group(1) if match else None


def _is_boilerplate_src(src):
    lower = src.lower()
    return any(hint in lower for hint in SCORM_BOILERPLATE_SCRIPT_HINTS)


def _is_boilerplate_script(attrs, body):
    """A script is boilerplate if it is a known wrapper file, or an inline block
    whose only logic is LMS API/pipwerks plumbing."""
    src = _script_src(attrs)
    if src is not None:
        return _is_boilerplate_src(src)
    lower = body.lower()
    if "pipwerks" in lower:
        return True
    return bool(SCORM_API_CALL_RE.search(body))


def strip_scorm_boilerplate(html):
    """Return ``html`` with SCORM API boilerplate ``<script>`` tags removed.

    Boilerplate wrapper ``src=`` tags and inline plumbing blocks are dropped so
    residual interactivity can be judged; content scripts are left in place.
    """

    def replace(match):
        if _is_boilerplate_script(match.group(1), match.group(2)):
            return ""
        return match.group(0)

    return _SCRIPT_TAG_RE.sub(replace, html)


def _is_boilerplate_member(name):
    return name.lower().endswith(".js") and _is_boilerplate_src(name)


def has_assessment_semantics(index_html, member_names, item):
    """True when a webcontent resource carries assessment/score/tracking meaning.

    Signals (any one is enough): a HotPotatoes-generated page, an
    ``adlcp:masteryscore``, or non-boilerplate script writing a SCORM
    score/status. Boilerplate is discounted first so a plain SCO that merely
    talks to the LMS is not mistaken for an exercise.
    """
    lower = index_html.lower()
    if "hot potatoes" in lower:
        return True
    if any(g.lower() in lower for g in HOTPOTATOES_GLOBALS):
        return True
    if item.get("masteryscore"):
        return True
    # Discount SCORM API boilerplate before grepping for a score/status write:
    # a plain content SCO reports cmi.core.lesson_status on unload as part of that
    # plumbing, and must not be mistaken for an exercise. Only the index's own
    # scripts are inspected — wrapper .js members reference cmi.* as API surface.
    return bool(SCORM_SCORE_RE.search(strip_scorm_boilerplate(index_html)))


def _references(tag, media_name):
    """True when ``tag`` (or a nested ``<source>``) points at ``media_name``."""
    src = tag.get("src") or ""
    if src.split("/")[-1] == media_name:
        return True
    for source in tag.find_all("source"):
        if (source.get("src") or "").split("/")[-1] == media_name:
            return True
    return False


def single_media_member(leaf):
    """Return the archive-member path if the resource reduces to one media file.

    A resource qualifies only when, after excluding the index HTML and
    discounted SCORM boilerplate, exactly one member remains, it has a media
    extension, and the index body's only meaningful element references it. Any
    ambiguity (a stylesheet, a second script, a second media file) returns
    ``None`` — promotion is conservative.
    """
    files = leaf.get("files") or []
    index_file = leaf.get("index_file") or leaf.get("href")
    index_name = (index_file or "").split("/")[-1]

    remaining = []
    for member in files:
        name = member.split("/")[-1]
        if name == index_name:
            continue
        if _is_boilerplate_member(member):
            continue
        remaining.append(member)

    if len(remaining) != 1:
        return None
    media = remaining[0]
    ext = media.rsplit(".", 1)[-1].lower() if "." in media else ""
    if ext not in MEDIA_EXTENSIONS:
        return None

    body = BeautifulSoup(leaf.get("index_html") or "", "html5lib").find("body")
    if body is None:
        return None
    media_tags = body.find_all(_MEDIA_TAGS)
    if len(media_tags) != 1 or not _references(media_tags[0], media.split("/")[-1]):
        return None
    # The media element must be the resource's sole meaningful content: a page
    # that also carries prose or interactive controls is a richer article, so it
    # stays an HTML5/KPUB zip rather than collapsing to a bare media node.
    if body.get_text(strip=True):
        return None
    if body.find_all(["a", "form", "input", "button", "select", "textarea"]):
        return None
    return media
