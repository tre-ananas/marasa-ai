"""Local Ollama provider.

This is the "bring your own model" path: no API key, no cost, everything runs
on the user's machine. It speaks Ollama's native ``/api/chat`` endpoint, which
is OpenAI-ish but not identical (NDJSON stream instead of SSE).

Recommended model: ``qwen3:8b`` (Apache-2.0, strong multilingual incl.
Arabic, ~5 GB). See README "Models" for the alternatives.

Two details matter for a usable tutor on a small GPU:

* ``num_ctx`` — Ollama defaults to a 4K context, which is too small for the
  tutor system prompt plus a conversation. We raise it (8K by default, and
  ``MARASA_OLLAMA_NUM_CTX`` overrides it).
* ``think`` — Qwen3 ships a "thinking" mode whose output is discarded by this
  adapter anyway, so it is turned off explicitly: it wastes tokens and
  latency, and the thinking text never reaches the learner.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..config import get_settings
from .base import ModelInfo, StreamChunk, TurnRequest, Usage


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.num_ctx = settings.ollama_num_ctx

    @property
    def default_model(self) -> str:
        return self.model

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()

        models: list[ModelInfo] = []
        for entry in payload.get("models", []):
            details = entry.get("details") or {}
            models.append(
                ModelInfo(
                    id=entry.get("name", ""),
                    label=entry.get("name", ""),
                    free=True,
                    notes=f"{details.get('parameter_size', '?')} · local",
                    extra={"size": entry.get("size", 0)},
                )
            )
        return models

    async def stream(self, request: TurnRequest) -> AsyncIterator[StreamChunk]:
        body = {
            "model": request.model or self.model,
            "messages": [{"role": "system", "content": request.system}, *request.messages],
            "stream": True,
            "think": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=body
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = (event.get("message") or {}).get("content", "")
                    if delta:
                        yield StreamChunk(delta=delta)
                    if event.get("done"):
                        yield StreamChunk(
                            usage=Usage(
                                input_tokens=int(event.get("prompt_eval_count") or 0),
                                output_tokens=int(event.get("eval_count") or 0),
                                cost_usd=0.0,
                                billing_source="local",
                            )
                        )
