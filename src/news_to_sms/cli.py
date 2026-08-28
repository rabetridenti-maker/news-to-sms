"""Command-line entrypoint.

Reads configuration from ``.env`` (via :class:`Settings`) and allows a few
overrides as flags, then runs one pipeline pass. ``--dry-run`` forces the
``console`` provider so the whole flow can be exercised with no credentials.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import anyio
import httpx

from news_to_sms.archive import MarkdownArchive
from news_to_sms.config import Settings
from news_to_sms.dedup import StateStore
from news_to_sms.errors import ConfigError, FetchError, NewsError, ParseError
from news_to_sms.llm import LlmClient
from news_to_sms.pipeline import build_digest, run
from news_to_sms.sms import build_provider
from news_to_sms.sources import build_source


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="news-to-sms",
        description="Fetch today's news, sanitize it, split into SMS-sized pieces "
        "and send them from a fixed sender number via an SMS gateway.",
    )
    parser.add_argument("--dry-run", action="store_true", help="log messages instead of sending")
    parser.add_argument(
        "--provider", choices=["console", "webhook", "aliyun", "smsbao"], help="override SMS provider"
    )
    parser.add_argument("--recipient", action="append", dest="recipients", help="recipient phone number")
    parser.add_argument("--max-length", type=int, help="per-message character cap")
    parser.add_argument("--url", help="news source URL")
    parser.add_argument("--source", choices=["rss", "json"], help="news source type")
    parser.add_argument("--state", help="dedup state file path")
    parser.add_argument("--archive-dir", help="markdown archive directory")
    parser.add_argument("--log-level", help="logging level")
    parser.add_argument(
        "--digest-out",
        help="instead of sending, write today's AI-rewritten digest to this file "
        "(used by the GitHub Pages / Shortcut delivery)",
    )
    return parser


def _apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    updates: dict[str, object] = {}
    if args.dry_run:
        updates["sms_provider"] = "console"
    if args.provider:
        updates["sms_provider"] = args.provider
    if args.recipients:
        updates["sms_recipients"] = args.recipients
    if args.max_length is not None:
        updates["sms_max_length"] = args.max_length
    if args.url:
        updates["news_url"] = args.url
    if args.source:
        updates["news_source_type"] = args.source
    if args.state:
        updates["state_path"] = args.state
    if args.archive_dir:
        updates["archive_dir"] = args.archive_dir
    if args.log_level:
        updates["log_level"] = args.log_level
    return settings.model_copy(update=updates) if updates else settings


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline; returns a process exit code."""
    args = _build_parser().parse_args(argv)
    settings = _apply_overrides(Settings(), args)

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("news_to_sms")

    if settings.sms_recipients and settings.sms_provider != "console":
        log.info(
            "user recipients: %s via provider=%(provider)s dry_run=%(dry)s",
            settings.sms_recipients,
            {"provider": settings.sms_provider, "dry": settings.dry_run},
        )

    async def _main() -> object:
        limits = httpx.Limits(max_connections=5, max_keepalive_connections=2)
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            source = build_source(settings, client)
            now = datetime.now(timezone.utc)
            rewriter = None
            if settings.ai_api_key:
                rewriter = LlmClient(
                    client=client,
                    api_key=settings.ai_api_key,
                    model=settings.ai_model,
                    base_url=settings.ai_base_url,
                )
            if args.digest_out:
                return await build_digest(source=source, rewriter=rewriter, now=now, log=log)
            provider = build_provider(settings, client)
            state = StateStore(Path(settings.state_path))
            archive = MarkdownArchive(Path(settings.archive_dir))
            return await run(
                settings=settings,
                source=source,
                provider=provider,
                state=state,
                archive=archive,
                now=now,
                log=log,
                rewriter=rewriter,
            )

    try:
        result = anyio.run(_main)
    except (ConfigError, FetchError, ParseError) as exc:
        log.exception("run failed (%s)", type(exc).__name__)
        return 2 if isinstance(exc, ConfigError) else 1
    except NewsError as exc:
        log.exception("run failed (%s)", type(exc).__name__)
        return 1
    if args.digest_out and isinstance(result, str):
        Path(args.digest_out).write_text(result, encoding="utf-8")
        log.info("wrote digest to %s (%d chars)", args.digest_out, len(result))
    return 0
