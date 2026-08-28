"""End-to-end orchestration: fetch -> (AI rewrite) -> sanitize -> dedup -> segment -> send -> archive."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from news_to_sms.archive import MarkdownArchive
from news_to_sms.config import Settings
from news_to_sms.dedup import StateStore, hash_key
from news_to_sms.errors import ConfigError, LlmError, SendError
from news_to_sms.llm import LlmClient
from news_to_sms.sanitize import sanitize
from news_to_sms.segmenter import segment
from news_to_sms.sms.base import SmsProvider
from news_to_sms.sources.base import NewsSource
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
    source: NewsSource,
    rewriter: LlmClient | None,
    now: datetime,
    log: logging.Logger,
) -> str:
    """Return today's AI-rewritten digest as one plain-text block (no sending).

    Used by the serverless/GitHub Pages path: the Shortcut fetches this text.
    """
    items = await source.fetch(now=now)
    parts: list[str] = []
    for item in items:
        body = _build_body(item)
        if rewriter is not None:
            try:
                body = await rewriter.rewrite(item.title, item.summary)
            except LlmError as exc:
                log.warning("llm rewrite failed, using sanitized body: %s", exc)
                body = _build_body(item)
        parts.append(body)
    if not parts:
        return ""
    today = now.astimezone(timezone.utc).date().isoformat()
    blocks = "\n".join(f"{index}. {part}" for index, part in enumerate(parts, start=1))
    return f"【今日新闻】{today}\n{blocks}"
