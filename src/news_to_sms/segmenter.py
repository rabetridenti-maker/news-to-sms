"""Split a body into SMS-sized pieces (each <= ``limit`` characters).

The requirement is "切成 200 字 的一段" / "每条只能接收 200 字". Segmentation
prefers breaking at sentence-final punctuation, and only falls back to a raw
character cut (or a space/punctuation cut) when a single sentence exceeds the
cap. ``len`` counts Unicode code points, which matches how Chinese SMS length
is counted (one 字 = one code point).
"""

from __future__ import annotations

import re

# Split after sentence-final punctuation (keeping the delimiter on the left).
_SENTENCE_END_RE = re.compile(r"(?<=[。！？；!?;…\n])")
# A small bonus: preferred mid-sentence break characters for hard splitting.
_BREAK_CHARS = set("，。！？；、 ,.!?;、")

_MIN_BREAK_WINDOW = 0.5


def _split_sentences(text: str) -> list[str]:
    return [part for part in _SENTENCE_END_RE.split(text) if part]


def _find_break(text: str, limit: int) -> int:
    """Return the best cut index within ``text[:limit]`` (>= ``min_cut``).

    Prefers the last space/punctuation before ``limit``; if none is found in
    the second half of the window, hard-cuts at ``limit``.
    """
    window = text[:limit]
    min_cut = int(limit * _MIN_BREAK_WINDOW)
    for i in range(len(window) - 1, max(min_cut - 1, 0), -1):
        if window[i] in _BREAK_CHARS:
            return i + 1  # keep the break char with the first half
    return limit


def _hard_split(text: str, limit: int) -> list[str]:
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = _find_break(remaining, limit)
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    chunks.append(remaining)
    return chunks


def segment(text: str, limit: int) -> list[str]:
    """Split ``text`` into a list of pieces, each at most ``limit`` characters.

    Returns ``[]`` for blank input. Raises ``ValueError`` if ``limit < 1``.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")  # noqa: TRY003
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    buffer = ""
    for sentence in _split_sentences(text):
        if len(sentence) > limit:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_hard_split(sentence, limit))
        elif len(buffer) + len(sentence) <= limit:
            buffer += sentence
        else:
            chunks.append(buffer)
            buffer = sentence
    if buffer:
        chunks.append(buffer)
    return chunks
