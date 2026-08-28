"""RSS/Atom news source using ``feedparser`` for parsing at the boundary."""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import datetime, timezone

import feedparser

from news_to_sms.errors import ParseError
from news_to_sms.sources.base import NewsSource
from news_to_sms.types import NewsItem


def _parse_published(entry: Mapping[str, object]) -> datetime | None:
    raw = entry.get("published_parsed")
    if raw is None:
        raw = entry.get("updated_parsed")
    if not isinstance(raw, (tuple, time.struct_time)):
        return None
    fields = [int(value) for value in raw[:6]]
    if len(fields) < 6:
        return None
    return datetime(*fields, tzinfo=timezone.utc)


class RssSource(NewsSource):
    """Parses an RSS/Atom feed into typed :class:`NewsItem` objects."""

    async def fetch(self, *, now: datetime) -> list[NewsItem]:
        body = await self._get_body()
        feed = feedparser.parse(body)
        if feed.bozo and not feed.entries:
            detail = feed.get("bozo_exception")
            raise ParseError(self._url, str(detail) if detail else "unparseable feed")

        items: list[NewsItem] = []
        for entry in feed.entries:
            link = str(entry.get("link") or entry.get("id") or "")
            item_id = str(entry.get("id") or entry.get("guid") or entry.get("link") or "")
            if not item_id:
                continue  # cannot dedup without a stable id
            title = str(entry.get("title") or "").strip()
            summary = str(entry.get("summary") or entry.get("description") or "")
            published = _parse_published(entry)
            items.append(
                NewsItem(
                    id=item_id,
                    title=title or item_id,
                    url=link,
                    summary=summary,
                    published=published,
                )
            )
        return self._select(items, now)
