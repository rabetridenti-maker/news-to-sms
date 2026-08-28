"""Tests for the OpenAI-compatible LLM rewrite client."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from news_to_sms.errors import LlmError
from news_to_sms.llm import LlmClient

_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


@respx.mock
async def test_llm_rewrite_posts_and_returns_content():
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": "改写后的内容"}}]}))
    async with httpx.AsyncClient() as client:
        llm = LlmClient(client=client, api_key="k", model="glm-4-flash", base_url="https://open.bigmodel.cn/api/paas/v4")
        out = await llm.rewrite("标题", "正文")
    assert out == "改写后的内容"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer k"
    assert json.loads(request.content)["model"] == "glm-4-flash"


@respx.mock
async def test_llm_raises_on_http_error():
    respx.post(_URL).mock(return_value=httpx.Response(401))
    async with httpx.AsyncClient() as client:
        llm = LlmClient(client=client, api_key="bad", model="glm-4-flash", base_url="https://open.bigmodel.cn/api/paas/v4")
        with pytest.raises(LlmError):
            await llm.rewrite("t", "s")


@respx.mock
async def test_llm_raises_on_malformed_response():
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"unexpected": True}))
    async with httpx.AsyncClient() as client:
        llm = LlmClient(client=client, api_key="k", model="glm-4-flash", base_url="https://open.bigmodel.cn/api/paas/v4")
        with pytest.raises(LlmError):
            await llm.rewrite("t", "s")
