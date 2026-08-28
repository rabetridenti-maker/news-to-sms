"""Typed exceptions raised by news-to-sms.

Every failure mode in the pipeline is a distinct, typed error so callers can
`match` on it at the boundary (``main``) and so the boundary catch stays narrow.
The base classes carry no state; subclasses carry the structured fields that
make the failure diagnosable.
"""

from __future__ import annotations

from dataclasses import dataclass


class NewsError(Exception):
    """Base class for every error raised by this package."""


@dataclass(frozen=True, slots=True)
class ConfigError(NewsError):
    """Configuration is invalid or incomplete for the chosen provider."""

    field: str
    detail: str

    def __str__(self) -> str:
        return f"ConfigError[{self.field}]: {self.detail}"


@dataclass(frozen=True, slots=True)
class FetchError(NewsError):
    """Fetching the news source failed at the HTTP boundary."""

    url: str
    status: int | None
    detail: str

    def __str__(self) -> str:
        status = self.status if self.status is not None else "n/a"
        return f"FetchError[{status}] {self.url}: {self.detail}"


@dataclass(frozen=True, slots=True)
class ParseError(NewsError):
    """The fetched body could not be interpreted as the expected format."""

    url: str
    detail: str

    def __str__(self) -> str:
        return f"ParseError {self.url}: {self.detail}"


@dataclass(frozen=True, slots=True)
class SendError(NewsError):
    """A message could not be delivered by the SMS provider."""

    provider: str
    recipient: str
    detail: str

    def __str__(self) -> str:
        return f"SendError[{self.provider}] -> {self.recipient}: {self.detail}"


@dataclass(frozen=True, slots=True)
class LlmError(NewsError):
    """The AI rewrite call failed (transport, auth, or malformed response)."""

    detail: str

    def __str__(self) -> str:
        return f"LlmError: {self.detail}"
