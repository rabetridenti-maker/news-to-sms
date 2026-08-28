"""File-backed dedup store.

Records which news item ids have already been sent, keyed by calendar date, so a
feed refresh on the same day does not re-send an article. Entries older than
``retain_days`` are pruned so the file stays small.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path


def hash_key(item_id: str) -> str:
    """Stable digest of a news item's unique id (link/guid)."""
    return hashlib.sha256(item_id.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class StateStore:
    """Persists a set of seen item-hashes grouped by day."""

    path: Path
    retain_days: int = 14
    today: date = field(default_factory=date.today)
    _data: dict[str, list[str]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.load()

    @property
    def _today_key(self) -> str:
        return self.today.isoformat()

    def load(self) -> None:
        """Read state from disk; missing or invalid state yields an empty store."""
        path = self.path
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._data = {}
                return
            self._data = {
                str(day): [str(k) for k in keys]
                for day, keys in raw.items()
                if isinstance(keys, list)
            }
        else:
            self._data = {}
        self._prune()

    def save(self) -> None:
        """Persist state atomically (write-then-replace)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def seen(self, key: str) -> bool:
        """``True`` if ``key`` was already recorded on today's bucket."""
        return key in self._data.get(self._today_key, [])

    def mark(self, key: str) -> None:
        """Record ``key`` in today's bucket (idempotent)."""
        bucket = self._data.setdefault(self._today_key, [])
        if key not in bucket:
            bucket.append(key)

    def _prune(self) -> None:
        """Drop buckets older than ``retain_days`` (and any future-dated ones)."""
        try:
            cutoff = self.today - timedelta(days=self.retain_days)
        except (ValueError, OverflowError):
            self._data = {}
            return
        kept: dict[str, list[str]] = {}
        for day, keys in self._data.items():
            try:
                day_date = date.fromisoformat(day)
            except ValueError:
                continue
            if cutoff <= day_date <= self.today:
                kept[day] = keys
        self._data = kept
