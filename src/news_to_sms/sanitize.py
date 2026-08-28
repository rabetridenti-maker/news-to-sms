"""Turn raw news bodies into SMS-friendly plain text.

Removes markdown syntax, HTML tags, images, and emoji — the note requires
"不能图片表情". The output is single-line plain text, ready for segmentation.
"""

from __future__ import annotations

import html
import re

_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_HEADING_MARKER_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_QUOTE_RE = re.compile(r"^[ \t]{0,3}>[ \t]?", re.MULTILINE)
_HR_RE = re.compile(r"^[ \t]{0,3}(?:[-*_][ \t]*){3,}$", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"```[^\n]*\n(?:.*?\n)?```", re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TABLE_SEP_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$", re.MULTILINE)

# Emphasis / code markers that carry no meaning in a text message.
_EMPHASIS_MARKERS_RE = re.compile(r"(\*\*|__|\*|_|`|~~)")
# List bullets / numbered items at the start of a line.
_LIST_MARKER_RE = re.compile(r"(?m)^[ \t]*(?:[-*+]|[0-9]+[.)])[ \t]+")

# Emoji + variation selectors + regional indicators.
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U0001f1e0-\U0001f1ff"
    "\u2600-\u27bf"
    "\ufe0f"
    "\u2705\u274c\u2b50\u2764\u2b55"
    "]+",
    flags=re.UNICODE,
)

_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_NEWLINE_RE = re.compile(r"\s*\n\s*")


def _decode_entities(text: str) -> str:
    return html.unescape(text)


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    return _HTML_TAG_RE.sub(" ", _decode_entities(text))


def strip_markdown(text: str) -> str:
    """Remove markdown structure while keeping readable text."""
    text = _CODE_FENCE_RE.sub(" ", text)
    text = _IMAGE_RE.sub(" ", text)
    text = _TABLE_SEP_RE.sub(" ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _REF_LINK_RE.sub(r"\1", text)
    text = _HEADING_MARKER_RE.sub("", text)
    text = _QUOTE_RE.sub("", text)
    text = _HR_RE.sub(" ", text)
    text = _LIST_MARKER_RE.sub(" ", text)
    return _EMPHASIS_MARKERS_RE.sub("", text)


def strip_emojis(text: str) -> str:
    """Remove emoji and variation selectors."""
    return _EMOJI_RE.sub("", text)


def collapse_whitespace(text: str) -> str:
    """Collapse internal whitespace/newlines into single spaces."""
    text = _NEWLINE_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def sanitize(text: str) -> str:
    """Produce the final plain-text body to send over SMS.

    Order matters: HTML/entity decoding first (so decoded ``&amp;`` is not
    re-interpreted), then markdown, then emoji, finally whitespace collapse.
    """
    text = strip_html(text)
    text = strip_markdown(text)
    text = strip_emojis(text)
    text = collapse_whitespace(text)
    return text.strip()
