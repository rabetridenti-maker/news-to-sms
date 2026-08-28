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
    "你是一名每日新闻主编。请基于【新闻材料】里的内容，输出一份中文早报，必须严格包含以下五个部分，"
    "每部分用一行小标题分隔：\n"
    "1. 【一句·名句】——选一句动漫/影视/文艺作品的名言，优先动漫；直接给出中文译文，并标注出处（作品/作者）。\n"
    "2. 【今日要闻】——从材料中按影响力和重要性挑选，必须同时覆盖国内和国际新闻，比例大致均衡"
    "（国内2-3条 + 国际2-3条），最多6条，每条约一两句话，按重要性从高到低排序。宁可精选，不要罗列。\n"
    "3. 【AI 与硬件·详解】——挑1-3条与AI/芯片/硬件相关的最重要新闻，国内外均可，写详细（背景、影响、关键数据）。\n"
    "4. 【大佬预测】——基于AI/硬件新闻，概括行业大佬或资深工程师的观点/预测（可合理归纳，注明是观点）。\n"
    "5. 【GitHub 今日热门】——列出提供的GitHub热门仓库：名称+星标数+一句话说明。\n"
    "整体控制在500字以内。某个部分没有对应材料就写“今日暂无”。只输出正文，不要开场白或解释。"
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
