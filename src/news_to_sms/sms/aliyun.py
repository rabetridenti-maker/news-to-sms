"""Aliyun SMS provider (Dysmsapi ``SendSms``, 2017-05-25).

Uses the classic POP RPC ``HMAC-SHA1`` signature. The message is passed as a
template variable, so the account must have an approved template containing a
``${content}`` placeholder (which is what enforces the "no images/emojis" rule at
the vendor's side). If you instead hit a generic HTTP gateway, use
:class:`news_to_sms.sms.webhook.WebhookProvider`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from news_to_sms.errors import SendError
from news_to_sms.sms.base import SmsProvider

_ENDPOINT = "https://dysmsapi.aliyuncs.com/"
_ACTION = "SendSms"
_VERSION = "2017-05-25"
_REGION = "cn-hangzhou"


def percent_encode(value: str) -> str:
    """Aliyun URL-encoding: keep ``A-Za-z0-9 - _ . ~``, encode everything else."""
    return quote(value, safe="-_.~")


def _canonical_query(params: dict[str, str]) -> str:
    """Sort params by key and join as ``key=value`` with percent-encoded parts."""
    return "&".join(
        f"{percent_encode(key)}={percent_encode(params[key])}" for key in sorted(params)
    )


@dataclass(frozen=True, slots=True)
class AliyunCredentials:
    access_key_id: str
    access_key_secret: str


@dataclass(slots=True)
class AliyunProvider(SmsProvider):
    """Sends each segment via Aliyun ``SendSms``."""

    client: httpx.AsyncClient
    credentials: AliyunCredentials
    sign_name: str
    template_code: str
    name: str = "aliyun"

    def _common_params(self, *, recipient: str, text: str, nonce: str, timestamp: str) -> dict[str, str]:
        return {
            "AccessKeyId": self.credentials.access_key_id,
            "Action": _ACTION,
            "Format": "JSON",
            "PhoneNumbers": recipient,
            "RegionId": _REGION,
            "SignName": self.sign_name,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": nonce,
            "SignatureVersion": "1.0",
            "TemplateCode": self.template_code,
            "TemplateParam": json.dumps({"content": text}),
            "Timestamp": timestamp,
            "Version": _VERSION,
        }

    def _sign(self, params: dict[str, str]) -> str:
        string_to_sign = f"GET&{percent_encode('/')}&{percent_encode(_canonical_query(params))}"
        key = f"{self.credentials.access_key_secret}&"
        digest = hmac.new(key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(digest).decode("utf-8")

    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = self._common_params(recipient=recipient, text=text, nonce=str(uuid.uuid4()), timestamp=timestamp)
        params["Signature"] = self._sign(params)
        url = f"{_ENDPOINT}?{_canonical_query(params)}"
        try:
            response = await self.client.get(url)
        except httpx.HTTPError as exc:
            raise SendError(self.name, recipient, str(exc)) from exc
        self._check_response(response, recipient)

    @staticmethod
    def _check_response(response: httpx.Response, recipient: str) -> None:
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise SendError("aliyun", recipient, "non-JSON response") from exc
        if data.get("Code", "") != "OK":
            raise SendError("aliyun", recipient, f"{data.get('Code')}: {data.get('Message')}")
