"""End-to-end pipeline test (source -> sanitize -> segment -> send -> archive)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from news_to_sms.archive import MarkdownArchive
from news_to_sms.config import Settings
from news_to_sms.dedup import StateStore
from news_to_sms.errors import ConfigError
from news_to_sms.pipeline import build_digest, run
from news_to_sms.sms.base import SmsProvider
from news_to_sms.sources import build_source

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


class RecordingProvider(SmsProvider):
    name = "recording"

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        self.sent.append({"sender": sender, "recipient": recipient, "text": text})


def _settings(tmp_path, **overrides) -> Settings:
    base = {
        "_env_file": None,
        "news_url": "http://feed",
        "sms_recipients": ["13800000000"],
        "state_path": str(tmp_path / "state.json"),
        "archive_dir": str(tmp_path / "archive"),
    }
    base.update(overrides)
    return Settings(**base)


@respx.mock
async def test_pipeline_sends_and_archives(tmp_path):
    respx.get("http://feed").mock(return_value=httpx.Response(200, content=RSS_BODY))
    settings = _settings(tmp_path)
    async with httpx.AsyncClient() as client:
        provider = RecordingProvider()
        source = build_source(settings, client)
        state = StateStore(Path(settings.state_path), today=NOW.date())
        archive = MarkdownArchive(Path(settings.archive_dir))
        result = await run(
            settings=settings,
            source=source,
            provider=provider,
            state=state,
            archive=archive,
            now=NOW,
            log=logging.getLogger("test"),
        )

    assert result.fetched == 1
    assert result.new_items == 1
    assert result.messages_sent == 1
    assert len(provider.sent) == 1
    assert provider.sent[0]["recipient"] == "13800000000"
    assert "Item A" in provider.sent[0]["text"]
    assert result.archived is not None
    assert result.archived.exists()
    assert "Item A" in result.archived.read_text(encoding="utf-8")


@respx.mock
async def test_pipeline_skips_items_already_sent(tmp_path):
    respx.get("http://feed").mock(return_value=httpx.Response(200, content=RSS_BODY))
    settings = _settings(tmp_path)
    state_path = Path(settings.state_path)

    async with httpx.AsyncClient() as client:
        source = build_source(settings, client)
        first = RecordingProvider()
        await run(
            settings=settings,
            source=source,
            provider=first,
            state=StateStore(state_path, today=NOW.date()),
            archive=MarkdownArchive(Path(settings.archive_dir)),
            now=NOW,
            log=logging.getLogger("test"),
        )
        second = RecordingProvider()
        result = await run(
            settings=settings,
            source=build_source(settings, client),
            provider=second,
            state=StateStore(state_path, today=NOW.date()),
            archive=MarkdownArchive(Path(settings.archive_dir)),
            now=NOW,
            log=logging.getLogger("test"),
        )

    assert result.skipped == 1
    assert second.sent == []


async def test_pipeline_requires_recipients(tmp_path):
    settings = _settings(tmp_path, sms_recipients=[])
    async with httpx.AsyncClient() as client:
        source = build_source(settings, client)
        provider = RecordingProvider()
        state = StateStore(Path(settings.state_path), today=NOW.date())
        archive = MarkdownArchive(Path(settings.archive_dir))
        with pytest.raises(ConfigError):
            await run(
                settings=settings,
                source=source,
                provider=provider,
                state=state,
                archive=archive,
                now=NOW,
                log=logging.getLogger("test"),
            )


class FakeRewriter:
    """Records rewrite calls and returns a fixed text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    async def rewrite(self, title: str, summary: str) -> str:
        self.calls.append((title, summary))
        return self.text


@respx.mock
async def test_pipeline_uses_ai_rewrite(tmp_path):
    respx.get("http://feed").mock(return_value=httpx.Response(200, content=RSS_BODY))
    settings = _settings(tmp_path)
    rewriter = FakeRewriter("AI改写后的简报")
    async with httpx.AsyncClient() as client:
        provider = RecordingProvider()
        result = await run(
            settings=settings,
            source=build_source(settings, client),
            provider=provider,
            state=StateStore(Path(settings.state_path), today=NOW.date()),
            archive=MarkdownArchive(Path(settings.archive_dir)),
            now=NOW,
            log=logging.getLogger("test"),
            rewriter=rewriter,
        )
    assert result.messages_sent == 1
    assert provider.sent[0]["text"] == "AI改写后的简报"
    assert rewriter.calls == [("Item A", "desc & A")]


@respx.mock
async def test_build_digest_uses_ai_rewrite(tmp_path):
    respx.get("http://feed").mock(return_value=httpx.Response(200, content=RSS_BODY))
    settings = _settings(tmp_path)
    rewriter = FakeRewriter("AI简报")
    async with httpx.AsyncClient() as client:
        text = await build_digest(
            source=build_source(settings, client),
            rewriter=rewriter,
            now=NOW,
            log=logging.getLogger("test"),
        )
    assert "【今日新闻】" in text
    assert "AI简报" in text
