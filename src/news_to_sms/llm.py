"""OpenAI-compatible LLM client for the AI-rewrite step.

Calls ``POST {base_url}/chat/completions`` with a ``Bearer`` token. This works
with any OpenAI-compatible provider (智谱 GLM, DeepSeek, 硅基流动, …), so swapping
providers only changes the model/base_url in config.

Two modes:
- :meth:`rewrite` — condense one article into a short SMS-style brief (used by the
  send path).
- :meth:`compose_digest` — turn a bundle of news + GitHub trending into the full
  five-part daily digest (used by the GitHub Pages / Shortcut path).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from news_to_sms.errors import LlmError

_SIMPLE_REWRITE_PROMPT = (
    "你是一名中文新闻编辑。请把用户提供的新闻改写成简洁、通顺、口语化的中文简报，"
    "保留核心信息，去掉营销腔和冗余，一般控制在200字以内。不要输出标题，直接输出正文。"
)

_DIGEST_EDITOR_PROMPT = (
    "你是一名每日新闻主编。请基于【新闻材料】和【GitHub今日热门数据】，输出一份中文早报，"
    "严格包含以下五部分、每部分一行小标题，整个输出（含小标题和换行）控制在290字以内，精炼但不能省略任何一部分：\n"
    "1. 【名句】必须选一句动漫或电影/文艺作品的名言（优先动漫，禁止从新闻人物发言里选），给中文译文+出处。\n"
    "2. 【要闻】国内和国际各挑最重要1-2条，每条一句话。\n"
    "3. 【AI硬件】挑1条AI/芯片/硬件最重要信息，一句话；没有就写“今日暂无”。\n"
    "4. 【预测】1句行业大佬或资深工程师对AI/科技的预测或观点。\n"
    "5. 【GitHub】必须从【GitHub今日热门数据】里挑2个仓库，写成“名称 ★星标”。\n"
    "五个部分都必须出现，不得省略。只输出正文，不要开场白。"
)


@dataclass(frozen=True, slots=True)
class LlmClient:
    """Sends prompts to an OpenAI-compatible chat endpoint."""

    client: httpx.AsyncClient
    api_key: str
    model: str
    base_url: str

    async def rewrite(self, title: str, summary: str) -> str:
        """Return a short rewritten brief, or raise :class:`LlmError`."""
        user_content = f"标题：{title}\n正文：{summary}".strip()
        return await self._complete(_SIMPLE_REWRITE_PROMPT, user_content)

    async def compose_digest(self, material: str) -> str:
        """Return the full five-part daily digest, or raise :class:`LlmError`."""
        return await self._complete(_DIGEST_EDITOR_PROMPT, material)

    async def _complete(self, system_prompt: str, user_content: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
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
