"""Fetch today's GitHub trending via the official search API (no scraping).

Trending ≈ repos created recently sorted by stars. Works unauthenticated at low
volume; pass a ``token`` (``GITHUB_TOKEN`` in Actions) for a higher rate limit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from news_to_sms.errors import FetchError

_TRENDING_URL = "https://api.github.com/search/repositories"


async def fetch_github_trending(
    client: httpx.AsyncClient,
    *,
    since_days: int = 7,
    per_page: int = 5,
    token: str | None = None,
) -> str:
    """Return trending repos as a short ``- owner/repo ★stars: desc`` text block."""
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).date().isoformat()
    params = {"q": f"created:>{since}", "sort": "stars", "order": "desc", "per_page": str(per_page)}
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = await client.get(_TRENDING_URL, params=params, headers=headers)
        response.raise_for_status()
        items = response.json()["items"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise FetchError(_TRENDING_URL, None, f"github trending: {exc}") from exc

    lines: list[str] = []
    for item in items:
        desc = str(item.get("description") or "").strip()
        name = str(item.get("full_name") or item.get("name") or "unknown")
        stars = int(item.get("stargazers_count") or 0)
        line = f"- {name} ★{stars}" + (f": {desc}" if desc else "")
        lines.append(line)
    return "\n".join(lines)
