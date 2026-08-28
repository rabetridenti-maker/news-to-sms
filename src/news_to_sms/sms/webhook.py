"""Generic HTTP SMS gateway provider (the 校讯通 plug-in point).

POSTs a JSON payload to a configurable endpoint. This is the adapter for vendors
that expose a plain HTTP/SMS API: the ``sender`` (fixed number) travels in the
payload, and an optional bearer token is swapped in as the required vendor
credential. The payload shape matches what most gateways expect
(``{sender, recipient, text}``); if a vendor differs, subclass and override
:meth:`_payload`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from news_to_sms.errors import SendError
from news_to_sms.sms.base import SmsProvider

_SUCCESS_STATUS = {200, 201, 202}


@dataclass(slots=True)
class WebhookProvider(SmsProvider):
    """Sends each message as a JSON POST to ``url``."""

    client: httpx.AsyncClient
    url: str
    name: str = "webhook"
    token: str | None = None

    def __post_init__(self) -> None:
        if self.url == "":
            raise ValueError("WebhookProvider requires a non-empty url")  # noqa: TRY003

    def _payload(self, *, sender: str, recipient: str, text: str) -> dict[str, Any]:
        return {"sender": sender, "recipient": recipient, "text": text}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        payload = self._payload(sender=sender, recipient=recipient, text=text)
        try:
            response = await self.client.post(self.url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SendError(self.name, recipient, str(exc)) from exc
        if response.status_code not in _SUCCESS_STATUS:
            raise SendError(self.name, recipient, f"HTTP {response.status_code}: {response.text[:200]}")
