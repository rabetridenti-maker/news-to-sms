#!/usr/bin/env bash
# cron runner. Schedule e.g.:  0 8 * * * /path/to/news-to-sms/scripts/run.sh >> /path/to/run.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi

exec "$PY" -m news_to_sms
