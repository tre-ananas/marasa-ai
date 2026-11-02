"""Provider interface.

A provider turns a turn request into a stream of text chunks plus usage
metadata. Four implementations are planned:

- ``mock``    offline, deterministic (default; used by tests)
- ``console`` OpenCode Console / OpenCode Go inference API (user's own budget)
- ``local``   a locally running OpenCode V2 server (``opencode serve``)
- ``ollama``  a local Ollama model

Everything above this layer (prompts, note parsing, assessment, PDF export) is
provider-agnostic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    allowance_usd: float | None = None
    billing_source: str | None = None


@dataclass
class TurnRequest:
    session_id: str
    system: str
    messages: list[dict[str, str]]
    model: str
    temperature: float = 0.8
    max_tokens: int = 900


@dataclass
class StreamChunk:
    delta: str = ""
    usage: Usage | None = None
    raw: dict | None = None


@dataclass
class ModelInfo:
    id: str
    label: str
    free: bool = False
    endpoint: str = ""
    context: int = 0
    notes: str = ""
    extra: dict = field(default_factory=dict)


class Provider(Protocol):
    name: str

    async def list_models(self) -> list[ModelInfo]: ...

    def stream(self, request: TurnRequest) -> AsyncIterator[StreamChunk]: ...
