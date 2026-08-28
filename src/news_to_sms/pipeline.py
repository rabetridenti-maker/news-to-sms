"""End-to-end orchestration: fetch -> (AI rewrite) -> sanitize -> dedup -> segment -> send -> archive."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from news_to_sms.archive import MarkdownArchive
from news_to_sms.config import Settings
from news_to_sms.dedup import StateStore, hash_key
from news_to_sms.errors import ConfigError, FetchError, LlmError, SendError
from news_to_sms.llm import LlmClient
from news_to_sms.sanitize import sanitize
from news_to_sms.segmenter import segment
from news_to_sms.sms.base import SmsProvider
from news_to_sms.sources.base import NewsSource
from news_to_sms.sources.github_trending import fetch_github_trending
from news_to_sms.types import NewsItem


@dataclass(frozen=True, slots=True)
class RunResult:
    """Observable outcomes of a single run."""

    fetched: int
    new_items: int
    messages_sent: int
    messages_failed: int
    skipped: int
    archived: Path | None


def _build_body(item: NewsItem) -> str:
    """Title + sanitised summary, joined as an SMS-ready plain-text body."""
    title = sanitize(item.title)
    summary = sanitize(item.summary)
    if summary:
        return f"{title}\n{summary}" if title else summary
    return title


async def run(
    *,
    settings: Settings,
    source: NewsSource,
    provider: SmsProvider,
    state: StateStore,
    archive: MarkdownArchive,
    now: datetime,
    log: logging.Logger,
    rewriter: LlmClient | None = None,
) -> RunResult:
    """Execute one pipeline pass and return the outcome summary."""
    if not settings.sms_recipients:
        raise ConfigError("sms_recipients", "at least one recipient is required")

    items = await source.fetch(now=now)
    fetched = len(items)

    new_items = 0
    messages_sent = 0
    messages_failed = 0
    skipped = 0
    last_archived: Path | None = None

    for item in items:
        key = hash_key(item.id)
        if state.seen(key):
            skipped += 1
            continue

        body = _build_body(item)
        if rewriter is not None:
            try:
                body = await rewriter.rewrite(item.title, item.summary)
            except LlmError as exc:
                log.warning("llm rewrite failed, using sanitized body: %s", exc)
                body = _build_body(item)
        chunks = segment(body, settings.sms_max_length)
        if not chunks:
            continue

        all_ok = True
        for recipient in settings.sms_recipients:
            for chunk in chunks:
                try:
                    await provider.send(
                        sender=settings.sms_sender,
                        recipient=recipient,
                        text=chunk,
                    )
                    messages_sent += 1
                except SendError as exc:  # noqa: PERF203
                    log.warning("send failed: %s", exc)
                    messages_failed += 1
                    all_ok = False

        if all_ok:
            state.mark(key)
            last_archived = archive.append(item, body, day=now.astimezone(timezone.utc).date())
            new_items += 1

    state.save()
    log.info(
        "done: fetched=%d new=%d sent=%d failed=%d skipped=%d",
        fetched,
        new_items,
        messages_sent,
        messages_failed,
        skipped,
    )
    return RunResult(
        fetched=fetched,
        new_items=new_items,
        messages_sent=messages_sent,
        messages_failed=messages_failed,
        skipped=skipped,
        archived=last_archived,
    )


async def build_digest(
    *,
    sources: list[NewsSource],
    rewriter: LlmClient | None,
    client: httpx.AsyncClient,
    settings: Settings,
    now: datetime,
    log: logging.Logger,
) -> str:
    """Return today's digest as one plain-text block (no sending).

    Used by the serverless/GitHub Pages path: the Shortcut fetches this text.
    With a rewriter the LLM composes a five-part digest (quote / news / AI-hardware /
    expert predictions / GitHub trending); without one it falls back to a plain list.
    """
    blocks: list[str] = []
    for source in sources:
        try:
            fetched = await source.fetch(now=now)
            log.info("digest source %s: %d items", source.url, len(fetched))
            if fetched:
                body = "\n".join(f"- {_build_body(item)}" for item in fetched)
                blocks.append(f"【{_source_label(source.url)}】\n{body}")
        except FetchError as exc:  # noqa: PERF203
            log.warning("source %s unavailable: %s", source.url, exc)
    news_text = "\n\n".join(blocks)

    trending = ""
    try:
        trending = await fetch_github_trending(client, token=settings.github_token)
    except FetchError as exc:
        log.warning("github trending unavailable: %s", exc)

    if rewriter is not None:
        try:
            material = _digest_material(news_text, trending)
            digest = await rewriter.compose_digest(material)
            return _cap_digest(digest, _DIGEST_MAX_CHARS)
        except LlmError as exc:
            log.warning("llm digest failed, falling back to plain: %s", exc)
    return _cap_digest(_plain_digest(news_text, trending, now), _DIGEST_MAX_CHARS)


# One SMS segment holds ~70 Chinese characters; keep the digest inside that so
# 校讯通 (SMS) shows the whole message instead of truncating or dropping it.
_DIGEST_MAX_CHARS = 70


def _cap_digest(text: str, limit: int) -> str:
    """Guarantee the digest is at most ``limit`` characters, breaking at a line end."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    newline = cut.rfind("\n")
    if newline > limit // 2:
        return cut[:newline].rstrip()
    return cut.rstrip()


def _source_label(url: str) -> str:
    """Short human label for a source URL so the AI can tell 国内 from 国际."""
    lower = url.lower()
    if "ithome" in lower:
        return "国内·IT之家"
    if "bbci" in lower or "bbc.co.uk" in lower:
        return "国际·BBC"
    if "techcrunch" in lower:
        return "国际·TechCrunch"
    if "ycombinator" in lower:
        return "国际·HackerNews"
    from urllib.parse import urlparse

    return urlparse(url).netloc


def _digest_material(news_text: str, trending: str) -> str:
    sections = [f"【今日新闻材料】\n{news_text}" if news_text else "【今日新闻材料】今日无新闻"]
    if trending:
        sections.append(f"【GitHub今日热门数据】\n{trending}")
    return "\n\n".join(sections)


def _plain_digest(news_text: str, trending: str, now: datetime) -> str:
    today = now.astimezone(timezone.utc).date().isoformat()
    parts: list[str] = [f"【今日新闻】{today}"]
    if news_text:
        parts.append(news_text)
    if trending:
        parts.append(f"【GitHub 今日热门】\n{trending}")
    return "\n\n".join(parts)
