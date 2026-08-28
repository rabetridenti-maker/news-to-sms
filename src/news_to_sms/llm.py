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
    "你是一只猫娘主编，给主人整理新闻早报。语气带一点可爱的猫娘味（偶尔加“喵”“~”“的说”即可），"
    "但**结构必须严格规范**。请严格按下面固定的五个部分、每个部分以指定小标题开头来写，顺序不能乱，五部分都要出现，"
    "不要发明其它标题。内容按【新闻材料】和【GitHub今日热门数据】来，要准确。"
    "整个输出（含小标题和换行）控制在300字以内，语气可爱但别影响内容。\n"
    "【名句】一句动漫或电影/文艺作品的名言（优先动漫）+出处。\n"
    "【要闻】优先科技/AI/硬件类，国内外各1-2条，每条一句话。\n"
    "【AI 和 硬件】挑1条AI/芯片/硬件最重要信息，一句话。\n"
    "【预测】1句行业大佬或资深工程师对AI/科技的预测或观点。\n"
    "【GitHub】从【GitHub今日热门数据】挑2个仓库：名称 ★星标。\n"
    "只输出正文，不要开场白。"
)

_DIGEST_EDITOR_PROMPT_AFTERNOON = (
    "你是一只猫娘主编，给主人整理下午的新闻摘要。语气带一点可爱的猫娘味（偶尔加“喵”“~”“的说”即可），"
    "但**结构必须严格规范**。请严格按下面固定的五个部分、每个部分以指定小标题开头来写，顺序不能乱，五部分都要出现，"
    "不要发明其它标题。内容按【新闻材料】和【GitHub今日热门数据】来，要准确。"
    "整个输出（含小标题和换行）控制在300字以内，语气可爱但别影响内容。\n"
    "【名句】一句动漫或电影/文艺作品的名言（优先动漫）+出处。\n"
    "【要闻】优先选军事、民生、社会、国际时事等（非科技类也要，军事科技也行）的重要新闻，国内外各1-2条，每条一句话。\n"
    "【军事科技】挑1条军事或国防科技相关的最重要信息，一句话。\n"
    "【预测】1句行业大佬或资深工程师对科技/国际形势的预测或观点。\n"
    "【GitHub】从【GitHub今日热门数据】挑2个仓库：名称 ★星标。\n"
    "只输出正文，不要开场白。"
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

    async def compose_digest(self, material: str, *, prompt: str = _DIGEST_EDITOR_PROMPT) -> str:
        """Return the daily digest with the given system prompt, or raise :class:`LlmError`."""
        return await self._complete(prompt, material)

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
