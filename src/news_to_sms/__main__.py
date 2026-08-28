"""Allow ``python -m news_to_sms``."""

from __future__ import annotations

import sys

from news_to_sms.cli import main

if __name__ == "__main__":
    sys.exit(main())
