"""Unit tests for the file-backed dedup store."""

from __future__ import annotations

from datetime import date

from news_to_sms.dedup import StateStore, hash_key


def test_hash_key_is_stable():
    assert hash_key("abc") == hash_key("abc")
    assert hash_key("abc") != hash_key("abd")


def test_seen_and_mark_round_trip(tmp_path):
    state = StateStore(tmp_path / "s.json", today=date(2025, 1, 1))
    assert state.seen("key") is False
    state.mark("key")
    state.save()
    reloaded = StateStore(tmp_path / "s.json", today=date(2025, 1, 1))
    assert reloaded.seen("key") is True


def test_seen_is_per_day(tmp_path):
    first = StateStore(tmp_path / "s.json", today=date(2025, 1, 1))
    first.mark("key")
    first.save()
    next_day = StateStore(tmp_path / "s.json", today=date(2025, 1, 2))
    assert next_day.seen("key") is False


def test_prune_drops_old_days_and_keeps_recent(tmp_path):
    state = StateStore(tmp_path / "s.json", today=date(2025, 2, 1), retain_days=7)
    state._data = {"2025-01-01": ["x"], "2025-01-31": ["y"]}
    state._prune()
    assert "2025-01-01" not in state._data
    assert "2025-01-31" in state._data


def test_invalid_state_resets_to_empty(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not valid json", encoding="utf-8")
    state = StateStore(path)
    assert state._data == {}
