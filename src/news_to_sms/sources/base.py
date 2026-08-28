"""News source boundary: fetch a body, parse it into typed :class:`NewsItem`, and
select the "recent" subset. Subclasses only implement :meth:`NewsSource.fetch` for
parsing; windowing/limiting is shared here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import httpx

from news_to_sms.errors import FetchError
from news_to_sms.types import NewsItem


class NewsSource(ABC):
    """A source of news items for a single run."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        window_hours: int,
        max_items: int,
    ) -> None:
        self._client = client
        self._url = url
        self._window_hours = window_hours
        self._max_items = max_items

    @abstractmethod
    async def fetch(self, *, now: datetime) -> list[NewsItem]:
        """Fetch and return items, newest first, already windowed + limited."""

    def _select(self, items: list[NewsItem], now: datetime) -> list[NewsItem]:
        """Keep items published within the window, newest first, then limit."""
        recent = [item for item in items if self._in_window(item, now)]
        recent.sort(key=lambda item: item.published or now, reverse=True)
        return recent[: self._max_items]

    def _in_window(self, item: NewsItem, now: datetime) -> bool:
        published = item.published
        if published is None:
            # Cannot verify freshness; allow it (dedup prevents re-sends).
            return True
        if self._window_hours > 0:
            return published <= now and (now - published) <= timedelta(hours=self._window_hours)
        return published.date() == now.date()

    @property
    def url(self) -> str:
        return self._url

    async def _get_body(self) -> bytes:
        """GET ``self._url`` and return the body, raising :class:`FetchError` on
        transport or non-2xx failure."""
        try:
            response = await self._client.get(self._url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise FetchError(self._url, None, str(exc)) from exc
        if response.status_code != 200:
            raise FetchError(self._url, response.status_code, response.reason_phrase)
        return response.content
