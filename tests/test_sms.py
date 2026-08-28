"""Tests for the SMS provider layer (console, webhook, aliyun)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from news_to_sms.errors import SendError
from news_to_sms.sms.aliyun import (
    AliyunCredentials,
    AliyunProvider,
    _canonical_query,
    percent_encode,
)
from news_to_sms.sms.base import SmsProvider
from news_to_sms.sms.smsbao import SmsBaoProvider
from news_to_sms.sms.webhook import WebhookProvider


class RecordingProvider(SmsProvider):
    """In-memory fake: records every send, never touches the network."""

    name = "recording"

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        self.sent.append({"sender": sender, "recipient": recipient, "text": text})


@respx.mock
async def test_webhook_sends_json_payload_and_bearer_token():
    route = respx.post("http://gw/sms").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as client:
        provider = WebhookProvider(client=client, url="http://gw/sms", token="tok")
        await provider.send(sender="1069", recipient="13800000000", text="你好")
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tok"
    assert json.loads(request.content) == {"sender": "1069", "recipient": "13800000000", "text": "你好"}


@respx.mock
async def test_webhook_raises_send_error_on_http_failure():
    respx.post("http://gw/sms").mock(return_value=httpx.Response(500, text="boom"))
    async with httpx.AsyncClient() as client:
        provider = WebhookProvider(client=client, url="http://gw/sms")
        with pytest.raises(SendError):
            await provider.send(sender="1069", recipient="13800000000", text="x")


def test_aliyun_percent_encode_matches_spec():
    assert percent_encode("a b") == "a%20b"
    assert percent_encode("a+b") == "a%2Bb"
    assert percent_encode("a/b") == "a%2Fb"
    assert percent_encode("A-Z_~") == "A-Z_~"


def test_aliyun_canonical_query_sorts_params():
    assert _canonical_query({"b": "2", "a": "1"}) == "a=1&b=2"


@respx.mock
async def test_aliyun_send_ok_posts_to_dysmsapi():
    route = respx.get(url__startswith="https://dysmsapi.aliyuncs.com/").mock(
        return_value=httpx.Response(200, json={"Code": "OK"})
    )
    async with httpx.AsyncClient() as client:
        provider = AliyunProvider(
            client=client,
            credentials=AliyunCredentials(access_key_id="AK", access_key_secret="SK"),
            sign_name="签名",
            template_code="SMS_1",
        )
        await provider.send(sender="1069", recipient="13800000000", text="内容")
    assert route.called


@respx.mock
async def test_aliyun_raises_send_error_on_vendor_error_code():
    respx.get(url__startswith="https://dysmsapi.aliyuncs.com/").mock(
        return_value=httpx.Response(200, json={"Code": "isv.INVALID_PARAMETERS", "Message": "bad"})
    )
    async with httpx.AsyncClient() as client:
        provider = AliyunProvider(
            client=client,
            credentials=AliyunCredentials(access_key_id="AK", access_key_secret="SK"),
            sign_name="签名",
            template_code="SMS_1",
        )
        with pytest.raises(SendError):
            await provider.send(sender="1069", recipient="13800000000", text="内容")


@respx.mock
async def test_smsbao_sends_with_signature_prepended():
    route = respx.get("https://api.smsbao.com/sms").mock(
        return_value=httpx.Response(200, json={"code": "0", "msg": "ok", "data": {"taskId": "1"}})
    )
    async with httpx.AsyncClient() as client:
        provider = SmsBaoProvider(client=client, username="user", apikey="k")
        await provider.send(sender="【新闻速递】", recipient="13800000000", text="今日要闻")
    request = route.calls.last.request
    params = dict(request.url.params)
    assert params["u"] == "user"
    assert params["p"] == "k"
    assert params["m"] == "13800000000"
    assert params["f"] == "json"
    assert params["c"] == "【新闻速递】今日要闻"


@respx.mock
async def test_smsbao_raises_send_error_on_nonzero_code():
    respx.get("https://api.smsbao.com/sms").mock(return_value=httpx.Response(200, json={"code": "41", "msg": "余额不足"}))
    async with httpx.AsyncClient() as client:
        provider = SmsBaoProvider(client=client, username="user", apikey="k")
        with pytest.raises(SendError):
            await provider.send(sender="【新闻速递】", recipient="13800000000", text="今日要闻")


@respx.mock
async def test_smsbao_handles_plain_text_error_response():
    respx.get("https://api.smsbao.com/sms").mock(return_value=httpx.Response(200, text="40"))
    async with httpx.AsyncClient() as client:
        provider = SmsBaoProvider(client=client, username="user", apikey="k")
        with pytest.raises(SendError):
            await provider.send(sender="", recipient="13800000000", text="x")
