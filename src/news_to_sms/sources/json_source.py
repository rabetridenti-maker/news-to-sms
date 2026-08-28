"""Generic JSON news source.

Accepts a root list of items, or an object with an ``items``/``data`` list. Each
item is validated at the boundary into a typed :class:`JsonItem` and then into a
:class:`NewsItem`. Common field aliases are accepted so real endpoints rarely need
a schema change.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from news_to_sms.errors import ParseError
from news_to_sms.sources.base import NewsSource
from news_to_sms.types import NewsItem


class JsonItem(BaseModel):
    """A single item from the JSON endpoint, parsed at the boundary."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    title: str = Field(validation_alias=AliasChoices("title", "headline", "name"))
    url: str = Field(default="", validation_alias=AliasChoices("url", "link", "href"))
    summary: str = Field(
        default="",
        validation_alias=AliasChoices("summary", "description", "content", "text", "body"),
    )
    published: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "published", "published_at", "date", "pubDate", "pub_date", "created_at", "timestamp"
        ),
    )

    @field_validator("id", "title", "url", "summary", mode="before")
    @classmethod
    def _coerce_text(cls, value: object) -> str:
        return "" if value is None else str(value)

    @model_validator(mode="after")
    def _normalise_timezone(self) -> JsonItem:
        if self.published is not None and self.published.tzinfo is None:
            self.published = self.published.replace(tzinfo=timezone.utc)
        return self

    @field_validator("published", mode="before")
    @classmethod
    def _parse_timestamp(cls, value: object) -> object:
        if value is None or isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not value.strip():
            return value
        text = value.strip()
        # RFC 2822 (RSS pubDate) e.g. "Wed, 01 Jan 2025 08:00:00 GMT".
        try:
            return parsedate_to_datetime(text)
        except (TypeError, ValueError):
            pass
        # ISO 8601; normalise a trailing "Z" to an explicit UTC offset.
        if text.endswith("Z"):
            return text[:-1] + "+00:00"
        return text


class JsonSource(NewsSource):
    """Parses a JSON endpoint into typed :class:`NewsItem` objects."""

    async def fetch(self, *, now: datetime) -> list[NewsItem]:
        body = await self._get_body()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise ParseError(self._url, f"invalid JSON: {exc}") from exc
        raw_items = self._extract_items(payload)
        return self._select(self._parse_items(raw_items), now)

    def _extract_items(self, payload: object) -> list[dict[str, object]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "data", "articles", "news"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            # A bare object that looks like one item (has a title).
            if "title" in payload or "headline" in payload:
                return [payload]
        raise ParseError(self._url, "unrecognised JSON shape (expected a list or {'items': [...]})")

    def _parse_items(self, raw_items: list[dict[str, object]]) -> list[NewsItem]:
        items: list[NewsItem] = []
        for raw in raw_items:
            try:
                parsed = JsonItem.model_validate(raw)
            except ValidationError as exc:
                raise ParseError(self._url, f"invalid item: {exc}") from exc
            item_id = parsed.id or parsed.url or parsed.title
            if not item_id:
                continue
            items.append(
                NewsItem(
                    id=item_id,
                    title=parsed.title or item_id,
                    url=parsed.url,
                    summary=parsed.summary,
                    published=parsed.published,
                )
            )
        return items
