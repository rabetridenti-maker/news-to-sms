"""Configuration loaded from the environment (``.env``).

Values are parsed once at the boundary into a typed :class:`Settings`; the rest
of the pipeline never re-reads the environment. Field names are snake_case;
pydantic-settings maps ``SMS_PROVIDER`` -> ``sms_provider`` automatically.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated settings for a single run."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- runtime ------------------------------------------------------------
    sms_provider: Literal["console", "webhook", "aliyun", "smsbao"] = "console"
    dry_run: bool = True

    # ---- news source ---------------------------------------------------------
    news_source_type: Literal["rss", "json"] = "rss"
    news_url: str = "https://example.com/feed.xml"
    news_window_hours: int = Field(default=24, ge=0)
    news_max_items: int = Field(default=10, ge=1)

    # ---- SMS ------------------------------------------------------------------
    sms_sender: str = "10690000"
    sms_recipients: Annotated[list[str], NoDecode] = Field(default_factory=list)
    sms_max_length: int = Field(default=200, ge=1)

    # ---- generic HTTP gateway -------------------------------------------------
    sms_webhook_url: str | None = None
    sms_webhook_token: str | None = None

    # ---- Aliyun SMS -----------------------------------------------------------
    aliyun_access_key_id: str | None = None
    aliyun_access_key_secret: str | None = None
    aliyun_sign_name: str | None = None
    aliyun_template_code: str | None = None

    # ---- 短信宝 SMS -----------------------------------------------------------
    smsbao_username: str | None = None
    smsbao_apikey: str | None = None

    # ---- AI rewrite (optional) ------------------------------------------------
    ai_api_key: str | None = None
    ai_model: str = "glm-4-flash"
    ai_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # ---- GitHub trending (optional, for the digest) ----------------------------
    github_token: str | None = None

    # ---- storage ----------------------------------------------------------------
    state_path: str = "state/state.json"
    archive_dir: str = "archive"
    log_level: str = "INFO"

    @field_validator("sms_provider", "news_source_type", mode="before")
    @classmethod
    def _blank_choice_to_default(cls, value: object, info: ValidationInfo) -> object:
        """Coerce a blank env value ('' from an unset secret) back to its default.

        Keeps running under GitHub Actions where an unset secret expands to ``''``.
        """
        if value is None or value == "":
            field_name = info.field_name
            if field_name is None:
                return value
            return cls.model_fields[field_name].default
        return value

    @field_validator("sms_recipients", mode="before")
    @classmethod
    def _split_recipients(cls, value: object) -> list[str]:
        """Turn a comma-separated env string into a non-empty list of numbers."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(part).strip() for part in value if str(part).strip()]
        return [part.strip() for part in str(value).split(",") if part.strip()]

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()


class SegmentSize(BaseModel):
    """The per-message length cap shared across the pipeline."""

    max_length: int = Field(ge=1)
