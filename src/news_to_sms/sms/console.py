"""Console provider — the safe default. Logs the message instead of sending it.

Used when ``SMS_PROVIDER=console`` (and by the ``--dry-run`` path) so the whole
pipeline can be verified with zero credentials or cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from news_to_sms.sms.base import SmsProvider


@dataclass(frozen=True, slots=True)
class ConsoleProvider(SmsProvider):
    """Logs each message at INFO level; never performs a network call."""

    name: str = "console"
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("news_to_sms"))

    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        self.logger.info(
            "sms[%s] from=%s to=%s chars=%d body=%s",
            self.name,
            sender,
            recipient,
            len(text),
            text,
        )
