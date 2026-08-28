"""Per-day markdown archive of the news that was sent.

SMS itself is plain text ("不能图片表情"), but the note also asks for an "md 文件".
Each run appends the day's sent items to ``archive/<date>.md`` so there is a
human-readable record of everything that went out.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from news_to_sms.types import NewsItem

_HEADER = "# {date}\n\n"
_ITEM = "## {title}\n\n{text}\n\n[{url}]({url})\n\n---\n\n"


class MarkdownArchive:
    """Appends sanitised news items to ``<directory>/<date>.md``."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def append(self, item: NewsItem, text: str, *, day: date) -> Path:
        """Append one item to the archive for ``day``; returns the written path."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{day.isoformat()}.md"
        if not path.exists():
            path.write_text(_HEADER.format(date=day.isoformat()), encoding="utf-8")
        block = _ITEM.format(title=item.title, text=text, url=item.url)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(block)
        return path
