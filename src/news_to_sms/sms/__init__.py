"""SMS provider selection.

:func:`build_provider` maps an :class:`~news_to_sms.config.Settings` value plus a
shared :class:`httpx.AsyncClient` to a concrete :class:`SmsProvider`. It raises
:class:`ConfigError` when the chosen provider's required settings are missing.
"""

from __future__ import annotations

import httpx

from news_to_sms.config import Settings
from news_to_sms.errors import ConfigError
from news_to_sms.sms.aliyun import AliyunCredentials, AliyunProvider
from news_to_sms.sms.base import SmsProvider
from news_to_sms.sms.console import ConsoleProvider
from news_to_sms.sms.smsbao import SmsBaoProvider
from news_to_sms.sms.webhook import WebhookProvider

__all__ = [
    "AliyunProvider",
    "ConsoleProvider",
    "SmsBaoProvider",
    "SmsProvider",
    "WebhookProvider",
    "build_provider",
]


def build_provider(settings: Settings, client: httpx.AsyncClient) -> SmsProvider:
    """Construct the provider selected by ``settings.sms_provider``."""
    provider = settings.sms_provider
    match provider:
        case "console":
            return ConsoleProvider()
        case "webhook":
            if not settings.sms_webhook_url:
                raise ConfigError("sms_webhook_url", "required when sms_provider=webhook")
            return WebhookProvider(
                client=client,
                url=settings.sms_webhook_url,
                token=settings.sms_webhook_token,
            )
        case "aliyun":
            _require_aliyun(settings)
            return AliyunProvider(
                client=client,
                credentials=AliyunCredentials(
                    access_key_id=settings.aliyun_access_key_id or "",
                    access_key_secret=settings.aliyun_access_key_secret or "",
                ),
                sign_name=settings.aliyun_sign_name or "",
                template_code=settings.aliyun_template_code or "",
            )
        case "smsbao":
            _require_smsbao(settings)
            return SmsBaoProvider(
                client=client,
                username=settings.smsbao_username or "",
                apikey=settings.smsbao_apikey or "",
            )
        case _:
            raise ConfigError("sms_provider", f"unknown provider: {provider!r}")


def _require_smsbao(settings: Settings) -> None:
    if not settings.smsbao_username:
        raise ConfigError("smsbao_username", "required when sms_provider=smsbao")
    if not settings.smsbao_apikey:
        raise ConfigError("smsbao_apikey", "required when sms_provider=smsbao")


def _require_aliyun(settings: Settings) -> None:
    required: tuple[tuple[str, str | None], ...] = (
        ("aliyun_access_key_id", settings.aliyun_access_key_id),
        ("aliyun_access_key_secret", settings.aliyun_access_key_secret),
        ("aliyun_sign_name", settings.aliyun_sign_name),
        ("aliyun_template_code", settings.aliyun_template_code),
    )
    for field, value in required:
        if not value:
            raise ConfigError(field, "required when sms_provider=aliyun")
