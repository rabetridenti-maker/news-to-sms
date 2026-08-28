"""OpenAI-compatible LLM client for the AI-rewrite step.

Calls ``POST {base_url}/chat/completions`` with a ``Bearer`` token. This works
with any OpenAI-compatible provider (智谱 GLM, DeepSeek, 硅基流动, …), so swapping
providers only changes the model/base_url in config.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from news_to_sms.errors import LlmError

_SYSTEM_PROMPT = (
    "你是一名中文新闻编辑。请把用户提供的新闻改写成简洁、通顺、口语化的中文简报，"
    "保留核心信息，去掉营销腔和冗余，一般控制在200字以内。不要输出标题，直接输出正文。"
)


@dataclass(frozen=True, slots=True)
class LlmClient:
    """Sends a rewrite prompt to an OpenAI-compatible chat endpoint."""

    client: httpx.AsyncClient
    api_key: str
    model: str
    base_url: str

    async def rewrite(self, title: str, summary: str) -> str:
        """Return the rewritten news brief, or raise :class:`LlmError`."""
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"标题：{title}\n正文：{summary}".strip()},
            ],
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LlmError(str(exc)) from exc
        return content.strip()
