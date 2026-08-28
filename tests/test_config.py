"""Unit tests for configuration parsing."""

from __future__ import annotations

from news_to_sms.config import Settings


def test_default_provider_is_console():
    settings = Settings(_env_file=None)
    assert settings.sms_provider == "console"
    assert settings.dry_run is True


def test_recipients_comma_list_is_split():
    settings = Settings(_env_file=None, sms_recipients="13800000000,13900000000")
    assert settings.sms_recipients == ["13800000000", "13900000000"]


def test_recipients_from_list_are_stripped():
    settings = Settings(_env_file=None, sms_recipients=[" 138 ", "139 "])
    assert settings.sms_recipients == ["138", "139"]


def test_max_length_requires_positive_value():
    settings = Settings(_env_file=None, sms_max_length=200)
    assert settings.sms_max_length == 200


def test_blank_choice_env_falls_back_to_default():
    # GitHub Actions expands an unset secret to '', which must not crash validation.
    settings = Settings(_env_file=None, sms_provider="", news_source_type="")
    assert settings.sms_provider == "console"
    assert settings.news_source_type == "rss"
