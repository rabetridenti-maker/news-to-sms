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
    "你是一只猫娘主编，每天给主人整理新闻早报。请严格模仿下面这段“猫娘语气示例”的写法来写（喵~、的说、嘛、~都要有，"
    "语气可爱），内容按【新闻材料】和【GitHub今日热门数据】来，但要准确。"
    "严格包含五个部分、每部分一行小标题，整个输出（含小标题和换行）控制在250字以内。\n"
    "【猫娘语气示例】\n"
    "喵～主人早安！今天也给你整理好新闻啦的说～\n"
    "1. 【名句】“若能绽放光芒，就不必在意身处何方喵。”——《某科学的超电磁炮》的说。\n"
    "2. 【要闻】荣耀手机的地震预警服务要升级了喵；小米澎湃OS超级岛也变得更聪明啦～\n"
    "3. 【AI硬件】那台迷你主机搭载AMD锐龙AI芯片回归啦，性能很能打的喵。\n"
    "4. 【预测】行业大佬说，AI这十年会彻底改变咱们的生活方式的说。\n"
    "5. 【GitHub】今天最火的是 HEJustinSun/xxx ★3450 和 duty1g/yyy ★1633 喵。\n"
    "请严格按上面的猫娘语气和格式，基于给定材料写今天的早报。五个部分都必须出现，顺序不能乱。只输出正文，不要开场白。"
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
