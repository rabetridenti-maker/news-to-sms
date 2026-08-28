"""News source selection."""

from __future__ import annotations

import httpx

from news_to_sms.config import Settings
from news_to_sms.errors import ConfigError
from news_to_sms.sources.base import NewsSource
from news_to_sms.sources.json_source import JsonSource
from news_to_sms.sources.rss import RssSource

__all__ = ["JsonSource", "NewsSource", "RssSource", "build_source"]


def build_source(settings: Settings, client: httpx.AsyncClient) -> NewsSource:
    """Construct the news source selected by ``settings.news_source_type``."""
    match settings.news_source_type:
        case "rss":
            return RssSource(
                client,
                url=settings.news_url,
                window_hours=settings.news_window_hours,
                max_items=settings.news_max_items,
            )
        case "json":
            return JsonSource(
                client,
                url=settings.news_url,
                window_hours=settings.news_window_hours,
                max_items=settings.news_max_items,
            )
        case _:
            raise ConfigError("news_source_type", f"unknown source: {settings.news_source_type!r}")
