"""News source selection.

``NEWS_URL`` may hold several comma-separated URLs (same type); each becomes one
source so the digest can draw from multiple feeds (e.g. AI + hardware).
"""

from __future__ import annotations

import httpx

from news_to_sms.config import Settings
from news_to_sms.errors import ConfigError
from news_to_sms.sources.base import NewsSource
from news_to_sms.sources.json_source import JsonSource
from news_to_sms.sources.rss import RssSource

__all__ = ["JsonSource", "NewsSource", "RssSource", "build_source", "build_sources"]


def _split_urls(url: str) -> list[str]:
    return [part.strip() for part in url.split(",") if part.strip()]


def build_sources(settings: Settings, client: httpx.AsyncClient) -> list[NewsSource]:
    """Build one source per comma-separated URL in ``settings.news_url``."""
    urls = _split_urls(settings.news_url)
    if not urls:
        raise ConfigError("news_url", "at least one news URL is required")
    return [_build_one(settings, client, url) for url in urls]


def build_source(settings: Settings, client: httpx.AsyncClient) -> NewsSource:
    """Build a single source (the first URL). Kept for the send path."""
    return build_sources(settings, client)[0]


def _build_one(settings: Settings, client: httpx.AsyncClient, url: str) -> NewsSource:
    match settings.news_source_type:
        case "rss":
            return RssSource(
                client,
                url=url,
                window_hours=settings.news_window_hours,
                max_items=settings.news_max_items,
            )
        case "json":
            return JsonSource(
                client,
                url=url,
                window_hours=settings.news_window_hours,
                max_items=settings.news_max_items,
            )
        case _:
            raise ConfigError("news_source_type", f"unknown source: {settings.news_source_type!r}")
