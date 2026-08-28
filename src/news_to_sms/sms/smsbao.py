"""短信宝 (SmsBao) SMS provider.

Sends each message via the 短信宝 国内短信 API::

    GET https://api.smsbao.com/sms?u=USER&p=APIKEY&m=PHONE&c=CONTENT&f=json

``p`` is the ApiKey (from the backend / customer service) or the MD5 of the login
password. The recipient-visible "fixed sender" is the platform signature, which
短信宝 requires to be present at the start of the content — so the sender value
is prepended to the message body.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from news_to_sms.errors import SendError
from news_to_sms.sms.base import SmsProvider

_ENDPOINT = "https://api.smsbao.com/sms"

# 短信宝 返回码 -> human-readable description.
_ERRORS: dict[str, str] = {
    "30": "请求参数不全",
    "40": "账号或密码错误",
    "41": "余额不足",
    "42": "账号已过期",
    "43": "IP 地址限制",
    "44": "账号已被禁用",
    "51": "内容含有敏感词",
    "52": "手机号码格式不正确",
    "53": "没有可用的短信产品",
    "54": "试用账号无权调用此接口",
    "55": "错误的账号",
    "70": "模板格式不正确",
    "71": "验签失败",
}


@dataclass(slots=True)
class SmsBaoProvider(SmsProvider):
    """Sends each segment via the 短信宝 国内短信 API."""

    client: httpx.AsyncClient
    username: str
    apikey: str
    name: str = "smsbao"

    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        content = f"{sender}{text}" if sender else text
        params = {"u": self.username, "p": self.apikey, "m": recipient, "c": content, "f": "json"}
        try:
            response = await self.client.get(_ENDPOINT, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SendError(self.name, recipient, str(exc)) from exc

        body = response.text.strip()
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict):
            code = str(data.get("code", ""))
            msg = str(data.get("msg", ""))
        else:
            # Plain-text return (e.g. "0" success or an error code like "40").
            code, msg = body, ""
        if code != "0":
            hint = _ERRORS.get(code, "unknown error")
            raise SendError(self.name, recipient, f"code={code} {msg or hint}")
