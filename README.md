# news-to-sms

Fetch **today's news** from a URL, sanitize it to plain text (no images, no emojis, no
markdown), cut it into pieces of at most **200 字**, and send each piece as a **plain-text
SMS from a fixed sender number** — e.g. to a 校讯通 (school-parent) SMS channel — while also
writing a per-day **markdown archive** of what was sent.

This project implements the workflow sketched out in the handwritten note:

> 手机定时从 URL 爬取今天生成的新闻 → 切成 200 字的一段 → 发向接口（短信通道）→
> 每条只能接收 200 字，不能图片表情，同时留一个 md 文件。

## How it works

```
┌────────────┐   ┌──────────┐   ┌────────┐   ┌──────────┐   ┌───────────────┐
│ NewsSource │──▶│ sanitize │──▶│ segment│──▶│ SmsSender │──▶│ MarkdownArchive│
│ rss / json │   │ → plain  │   │ ≤200字 │   │ console/  │   │ archive/YYYY-MM│
│            │   │   text   │   │   each │   │ webhook/  │   │   -DD.md (each│
└────────────┘   └──────────┘   └────────┘   │ aliyun   │   │   news item)   │
                                             └──────────┘   └───────────────┘
```

A **StateStore** (`state/state.json`) records which news item ids were already sent, so a
feed refresh on the same day never re-sends an article.

## Requirements

- Python 3.10+
- Network access to the news URL and (for real sending) your SMS gateway

## Install

```bash
# with uv (recommended)
uv sync --extra dev

# or with pip
python -m venv .venv
. .venv/Scripts/activate        # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
```

## Configure

Copy `.env.example` to `.env` and fill it in (at minimum set `SMS_RECIPIENTS` and `NEWS_URL`).
A dry-run needs no cloud credentials — it logs the would-be messages:

```bash
# What to send, from a fixed number, to whom
SMS_PROVIDER=console        # console | webhook | aliyun
SMS_SENDER=10690000          # the fixed sender number seen by the recipient
SMS_RECIPIENTS=13800000000  # comma-separated 校讯通 subscriber numbers
SMS_MAX_LENGTH=200           # "每条只能接收 200 字"

# Where the news comes from
NEWS_SOURCE_TYPE=rss         # rss | json
NEWS_URL=https://example.com/feed.xml
NEWS_WINDOW_HOURS=24         # keep only items published within this window
NEWS_MAX_ITEMS=10

# Storage
STATE_PATH=state/state.json
ARCHIVE_DIR=archive
```

| Variable | Purpose |
|---|---|
| `SMS_PROVIDER` | `console` (log only), `webhook` (generic HTTP gateway), `aliyun` (Aliyun SMS), `smsbao` (短信宝) |
| `SMS_SENDER` | The fixed sender number / signature recipients see |
| `SMS_RECIPIENTS` | Comma-separated recipient phone numbers |
| `SMS_MAX_LENGTH` | Per-message character cap (default 200) |
| `NEWS_SOURCE_TYPE` | `rss` (RSS/Atom) or `json` (arbitrary endpoint) |
| `NEWS_URL` | One or more comma-separated news URLs (same type). The live digest mixes 国内 (IT之家) + 国际 (BBC / TechCrunch / Hacker News). |
| `NEWS_WINDOW_HOURS` | Keep articles published within this many hours (0 = today) |
| `NEWS_MAX_ITEMS` | Hard cap on items processed per run |
| `AI_API_KEY` | Optional: enable AI-rewriting each article with an OpenAI-compatible LLM |
| `AI_MODEL` | Model name (default `glm-4-flash`, the free 智谱 GLM) |
| `AI_BASE_URL` | OpenAI-compatible endpoint (default 智谱 `…/api/paas/v4`) |

## Run

A dry run needs `SMS_RECIPIENTS` set (use the `--recipient` flag to override):

```bash
# Dry run (default): logs the messages, sends nothing
.venv/Scripts/python -m news_to_sms --recipient 13800000000

# Or via the console script (reads recipients from .env)
.venv/Scripts/news-to-sms

# Dry run against the bundled sample feed (serve locally first)
.venv/Scripts/python -m news_to_sms --dry-run --url http://127.0.0.1:8000/news.xml --recipient 13800000000

# Actually send (after configuring a real provider + recipients)
SMS_PROVIDER=webhook SMS_WEBHOOK_URL=https://gw/sms .venv/Scripts/python -m news_to_sms
```

`--dry-run` forces the `console` provider, so you can verify the fetch → clean → segment
→ (pretend) send → archive flow without any provider credentials.

## AI rewrite (optional)

Set `AI_API_KEY` to have the news rewritten by an OpenAI-compatible LLM before
delivery.

- **Send path** (`run`): each article is condensed into a ≤200-字 brief before splitting.
- **Digest path** (`--digest-out`): the LLM picks today's single most important news item
  (domestic or international) and writes it as **one line ≤70 Chinese characters** — sized
  so a single SMS reaches 校讯通 intact instead of being truncated.

- Default model is the **free 智谱 GLM-4-Flash**; point `AI_MODEL`/`AI_BASE_URL` at any
  OpenAI-compatible provider (DeepSeek, 硅基流动, …).
- If the LLM call fails, the pipeline falls back to a plain numbered digest, so a hiccup
  never stops the delivery.

## Free automatic delivery: GitHub Pages + iPhone Shortcut

No server needed. A GitHub Actions workflow (`.github/workflows/daily-digest.yml`) runs
daily, AI-rewrites today's news, and publishes the result to GitHub Pages. Your iPhone
Shortcut fetches that URL and sends it to you as an iMessage (free, no SMS charges).

**One-time setup**
1. Push this repo to GitHub.
2. Repo **Settings → Pages → Source: "GitHub Actions"**.
3. Add repo **Secrets**: `AI_API_KEY` (your 智谱 key) and `NEWS_URL` (your news feed).
4. Run the `daily-digest` workflow once (Actions → workflow → "Run workflow") to publish
   the first digest.
5. Your digest is now at `https://<username>.github.io/<repo>/digest.txt`.

**iPhone Shortcut**
1. Open **快捷指令** → new shortcut → add **获取URL内容** → URL = the `digest.txt` address above.
2. Add **发送信息** → recipient = your own phone number, content = "来自上一步的URL内容".
3. Save. Then **个人自动化 → 特定时间 08:00 → 运行该快捷指令 → 关闭"运行前询问"**.

You can generate the digest locally too:
```bash
.venv/Scripts/python -m news_to_sms --digest-out digest.txt --url <你的新闻源URL>
```

## Choosing an SMS provider

The note targets a **fixed sender number** and a **短信-only 校讯通 channel**, so:

- **`console`** — safe default; logs each message. Use it to test the pipeline.
- **`webhook`** — the general 校讯通 / vendor HTTP gateway plug-in. It POSTs
  `{"sender": "...", "recipient": "...", "text": "..."}` to `SMS_WEBHOOK_URL`, with an
  optional `Bearer` token in `SMS_WEBHOOK_TOKEN`. Subclass
  `WebhookProvider` and override `_payload()` if your vendor uses a different body.
- **`aliyun`** — Aliyun SMS (`SendSms`, 2017-05-25). Requires an approved `SignName` and a
  template containing a `${content}` variable; the message is delivered as that variable.
  Set `ALIYUN_ACCESS_KEY_ID/SECRET`, `ALIYUN_SIGN_NAME`, `ALIYUN_TEMPLATE_CODE`.
- **`smsbao`** — 短信宝 国内短信 API, quickest for individuals (no separate sign/template
  approval flow). Sends `GET https://api.smsbao.com/sms?u=...&p=...&m=...&c=...`. Set
  `SMSBAO_USERNAME` and `SMSBAO_APIKEY` (the ApiKey from the backend, or the MD5 of your
  login password); set `SMS_SENDER` to your 短信宝 签名 (e.g. `【新闻速递】`), which is
  prepended to the message content.

## Scheduling

**Recommended for a fixed-number 校讯通 sender:** run this on a machine you control (the
gateway may require a trusted source and the sender number is bound to your account).

- **Windows Task Scheduler** → run `scripts/run.ps1` daily.
- **cron (macOS/Linux)** → run `scripts/run.sh` daily.
- **GitHub Actions** → `.github/workflows/daily-news.yml` (best for a public RSS/JSON source
  and a cloud SMS provider).

Example (Linux cron, 08:00 daily):
```
0 8 * * * cd /path/to/news-to-sms && .venv/bin/python -m news_to_sms >> run.log 2>&1
```

## Example feed

`examples/news.xml` is a tiny sample RSS file you can serve locally to try the flow:

```bash
cd examples && python -m http.server 8000
# in another shell:
.venv/Scripts/python -m news_to_sms --dry-run --url http://127.0.0.1:8000/news.xml
```

## Tests & quality gates

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check .
.venv/Scripts/basedpyright
```

The suite covers the segmenter, sanitizer, dedup store, config parsing, RSS/JSON fetching
(against HTTP via `respx`), each SMS provider, and an end-to-end pipeline run.

## Project layout

```
src/news_to_sms/
  cli.py          # argparse entrypoint
  config.py       # pydantic-settings config
  types.py        # NewsItem value object
  errors.py       # typed exceptions
  sanitize.py     # markdown/html/emoji -> plain text
  segmenter.py    # CJK-aware <=N 字 chunking
  dedup.py        # file-backed StateStore
  archive.py      # per-day markdown archive
  pipeline.py     # orchestration
  sources/        # rss.py, json_source.py, base.py
  sms/            # base.py, console.py, webhook.py, aliyun.py
```
