"""Integration tests for the RSS and JSON news sources against HTTP (respx)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from news_to_sms.errors import FetchError, ParseError
from news_to_sms.sources import build_sources
from news_to_sms.sources.github_trending import fetch_github_trending
from news_to_sms.sources.json_source import JsonSource
from news_to_sms.sources.rss import RssSource

NOW = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

RSS_BODY = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Example</title>
<item>
  <title>Item A</title>
  <link>http://a/1</link>
  <guid>a-1</guid>
  <description>desc &amp; A</description>
  <pubDate>Wed, 01 Jan 2025 08:00:00 GMT</pubDate>
</item>
</channel></rss>"""


@respx.mock
async def test_rss_fetch_parses_and_filters_recent():
    respx.get("http://feed").mock(return_value=httpx.Response(200, content=RSS_BODY))
    async with httpx.AsyncClient() as client:
        source = RssSource(client, url="http://feed", window_hours=24, max_items=5)
        items = await source.fetch(now=NOW)
    assert len(items) == 1
    assert items[0].id == "a-1"
    assert items[0].title == "Item A"
    assert items[0].url == "http://a/1"
    assert items[0].published == datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)


@respx.mock
async def test_rss_raises_fetch_error_on_non_200():
    respx.get("http://feed").mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        source = RssSource(client, url="http://feed", window_hours=24, max_items=5)
        with pytest.raises(FetchError):
            await source.fetch(now=NOW)


@respx.mock
async def test_json_fetch_parses_root_list():
    respx.get("http://api").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": "1", "title": "T", "url": "http://u/1", "summary": "s", "published": "2025-01-01T08:00:00Z"}],
        )
    )
    async with httpx.AsyncClient() as client:
        source = JsonSource(client, url="http://api", window_hours=24, max_items=5)
        items = await source.fetch(now=NOW)
    assert len(items) == 1
    assert items[0].id == "1"
    assert items[0].title == "T"
    assert items[0].published == datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)


@respx.mock
async def test_json_raises_parse_error_on_unrecognised_shape():
    respx.get("http://api").mock(return_value=httpx.Response(200, json={"foo": 1}))
    async with httpx.AsyncClient() as client:
        source = JsonSource(client, url="http://api", window_hours=24, max_items=5)
        with pytest.raises(ParseError):
            await source.fetch(now=NOW)


@respx.mock
async def test_github_trending_returns_repo_lines():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"full_name": "org/repo-a", "stargazers_count": 1234, "description": "an AI tool"},
                    {"full_name": "org/repo-b", "stargazers_count": 99, "description": None},
                ]
            },
        )
    )
    async with httpx.AsyncClient() as client:
        text = await fetch_github_trending(client)
    assert "- org/repo-a ★1234: an AI tool" in text
    assert "- org/repo-b ★99" in text


async def test_build_sources_splits_comma_separated_urls():
    from news_to_sms.config import Settings

    settings = Settings(_env_file=None, news_url="http://a/feed.xml, http://b/feed.xml")
    async with httpx.AsyncClient() as client:
        sources = build_sources(settings, client)
    assert len(sources) == 2
    assert [s.url for s in sources] == ["http://a/feed.xml", "http://b/feed.xml"]
