"""Provider registry."""

from __future__ import annotations

from ..config import get_settings
from .base import ModelInfo, Provider, StreamChunk, TurnRequest, Usage
from .mock import MockProvider
from .ollama import OllamaProvider

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


def get_provider(name: str | None = None) -> Provider:
    provider_name = (name or get_settings().provider).lower()

    if provider_name == "mock":
        return MockProvider()
    if provider_name == "ollama":
        return OllamaProvider()

    if provider_name in {"console", "go"}:
        raise ProviderUnavailable(
            "The OpenCode Console/Go provider lands in milestone M1 "
            "(backend/app/providers/opencode_console.py). Use MARASA_PROVIDER=mock "
            "or MARASA_PROVIDER=ollama until then."
        )
    if provider_name == "local":
        raise ProviderUnavailable(
            "The local OpenCode V2 server provider lands in milestone M1.5 "
            "(backend/app/providers/opencode_local.py). It needs OpenCode >= 2.x."
        )

    raise ProviderUnavailable(f"Unknown provider '{provider_name}'.")
