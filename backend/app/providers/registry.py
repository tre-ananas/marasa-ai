"""Provider registry."""

from __future__ import annotations

from ..config import get_settings
from .base import ModelInfo, Provider, StreamChunk, TurnRequest, Usage
from .mock import MockProvider
from .opencode_console import OpenCodeConsoleProvider

__all__ = [
    "ModelInfo",
    "Provider",
    "ProviderUnavailable",
    "StreamChunk",
    "TurnRequest",
    "Usage",
    "get_provider",
]


class ProviderUnavailable(RuntimeError):
    """Raised when a configured provider is not wired up yet."""


def get_provider(name: str | None = None, api_key: str | None = None) -> Provider:
    provider_name = (name or get_settings().provider).lower()

    if provider_name == "mock":
        return MockProvider()
    if provider_name in {"console", "go", "opencode"}:
        return OpenCodeConsoleProvider(api_key=api_key, endpoint="go")

    raise ProviderUnavailable(
        f"Unknown provider '{provider_name}'. Use 'console' for OpenCode Go."
    )
