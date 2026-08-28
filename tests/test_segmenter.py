"""Unit tests for the SMS-sized segmenter."""

from __future__ import annotations

import pytest

from news_to_sms.segmenter import segment


def test_segment_returns_single_chunk_within_limit():
    text = "今天天气不错。"
    assert segment(text, 200) == [text]


def test_segment_blank_returns_empty():
    assert segment("   ", 200) == []


def test_segment_rejects_limit_below_one():
    with pytest.raises(ValueError, match="limit must be >= 1"):
        segment("你好", 0)


def test_segment_splits_at_sentence_boundaries():
    chunks = segment("第一句。第二句。", 5)
    assert chunks == ["第一句。", "第二句。"]


def test_segment_never_exceeds_limit_and_preserves_content():
    text = "啊" * 500
    chunks = segment(text, 200)
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "".join(chunks) == text


def test_segment_hard_splits_long_punctuation_run():
    text = "，" * 300
    chunks = segment(text, 100)
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "".join(chunks) == text


def test_segment_exact_limit_is_single_chunk():
    assert segment("好" * 10, 10) == ["好" * 10]
