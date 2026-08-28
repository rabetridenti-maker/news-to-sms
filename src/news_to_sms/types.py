"""Domain value types.

Untrusted input (RSS/JSON bodies, raw summaries) is parsed into these typed
values at the source boundary and never re-validated inside the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class NewsItem:
    """A single, deduplicatable news item.

    ``id`` is the stable unique key (the link/guid when available), and
    ``summary`` is the raw body that still needs sanitising before sending.
    ``published`` may be ``None`` when a source does not expose a timestamp.
    """

    id: str
    title: str
    url: str
    summary: str
    published: datetime | None = None
