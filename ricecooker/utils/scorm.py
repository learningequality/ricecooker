"""Recognise SCORM LMS-communication boilerplate, which carries no content.

Pure functions over already-read HTML and member names; the caller does the I/O.
"""

import re

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
