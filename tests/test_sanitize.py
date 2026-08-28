"""Unit tests for sanitisation to plain SMS text."""

from __future__ import annotations

from news_to_sms.sanitize import sanitize


def test_sanitize_keeps_link_text():
    assert sanitize("[标题](http://example.com)") == "标题"


def test_sanitize_drops_images():
    assert sanitize("![图](http://example.com/a.png)") == ""


def test_sanitize_strips_html_tags_and_decodes_entities():
    assert sanitize("<b>Hello &amp; bye</b>") == "Hello & bye"


def test_sanitize_removes_emojis():
    assert sanitize("你好😀世界🎉") == "你好世界"


def test_sanitize_collapses_newlines_and_spaces():
    assert sanitize("好\n\n  的") == "好 的"


def test_sanitize_strips_heading_and_list_markers_but_keeps_text():
    assert sanitize("# 标题\n- 项目1\n- 项目2") == "标题 项目1 项目2"


def test_sanitize_strips_inline_code_emphasis():
    assert sanitize("用 `print` 和 **加粗** 输出") == "用 print 和 加粗 输出"
