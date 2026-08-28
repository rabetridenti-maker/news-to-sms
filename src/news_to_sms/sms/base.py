"""SMS delivery abstraction.

A provider delivers a single pre-segmented, <= ``max_length`` plain-text body to
one recipient. Providers raise :class:`SendError` on failure so the orchestrator
can report per-recipient failures without stopping the batch.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SmsProvider(ABC):
    """Sends one plain-text message to one recipient."""

    name: str = "base"

    @abstractmethod
    async def send(self, *, sender: str, recipient: str, text: str) -> None:
        """Deliver ``text`` to ``recipient``, raising :class:`SendError` on failure."""
