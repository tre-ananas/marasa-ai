"""OpenCode Go inference provider.

Talks to OpenCode's hosted Go inference API so a learner can spend their own
OpenCode Go subscription allowance on practice:

* ``https://opencode.ai/inference/go`` — the Go subscription endpoint

The endpoint serves several model families:

* OpenAI Chat Completions — ``/openai/v1/chat/completions``
* Anthropic Messages     — ``/anthropic/v1/messages``
* OpenAI Responses       — ``/openai/v1/responses`` (not implemented in the MVP)

The model catalogue at ``/v1/models`` says which family each model uses, so
the provider picks the right wire format per model.

Per the OpenCode Go guidance, requests carry a stable ``x-opencode-session``
header and a real user agent, so usage is attributed correctly and billed
against the right allowance.

The response usage block reports what the request cost and how much of the Go
allowance it consumed; both are surfaced in the session strip.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import get_settings
from .base import ModelInfo, StreamChunk, TurnRequest, Usage

USER_AGENT = "marasa-ai/0.1 (+https://github.com/tre-ananas/marasa-ai)"


class ProviderError(RuntimeError):
    """A failure worth showing the learner, with a suggested action."""

    def __init__(self, message: str, *, status: int = 0, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass
class _CatalogueEntry:
    model_id: str
    family: str = "chat-completions"
    free: bool = False
    label: str = ""
    context: int = 0


class OpenCodeConsoleProvider:
    name = "console"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.opencode_api_key
        self.endpoint = "go"
        self.base_url = settings.opencode_go_base_url.rstrip("/")

    @property
    def default_model(self) -> str:
        # Go requests always draw from the signed-in account's Go allowance.
        from ..config import DEFAULT_MODEL

        return DEFAULT_MODEL

    def _headers(self, session_id: str) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError(
                "No OpenCode Go API key is configured for this browser session. "
                "Sign in with OpenCode Go and try again.",
                status=401,
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": USER_AGENT,
            # A stable id per conversation, so OpenCode can route and cache
            # the session correctly.
            "x-opencode-session": session_id,
        }

    # ------------------------------------------------------------------ models

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.get(f"{self.base_url}/v1/models")
            if response.status_code >= 400:
                raise self._error_from_response(response)
            payload = response.json()

        models: list[ModelInfo] = []
        for entry in payload.get("data", []):
            catalogue = _CatalogueEntry(
                model_id=entry.get("id", ""),
                family=_family_of(entry),
                free=_is_free(entry),
                label=entry.get("name") or entry.get("id", ""),
                context=int((entry.get("limit") or {}).get("context") or 0),
            )
            if not catalogue.model_id:
                continue
            models.append(
                ModelInfo(
                    id=catalogue.model_id,
                    label=catalogue.label,
                    free=catalogue.free,
                    endpoint=catalogue.family,
                    context=catalogue.context,
                    notes="free" if catalogue.free else "paid",
                )
            )
        models.sort(key=lambda model: (not model.free, model.id))
        return models

    async def model_family(self, model_id: str) -> str:
        """Which wire format a model uses ("chat-completions" or "messages")."""
        try:
            models = await self.list_models()
        except ProviderError:
            return "chat-completions"
        for model in models:
            if model.id == model_id:
                return model.endpoint or "chat-completions"
        return "chat-completions"

    # ------------------------------------------------------------------- usage

    async def get_go_usage(self) -> dict:
        """Read the signed-in key's Go allowance windows.

        The endpoint is intentionally kept separate from inference: it requires
        the key's ``Usage: Read`` permission and reports percentages rather
        than dollar costs.
        """
        if not self.api_key:
            raise ProviderError(
                "No OpenCode Go API key is configured for this browser session.",
                status=401,
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://opencode.ai/zen/go/v1/usage",
                headers=headers,
            )
        if response.status_code >= 400:
            if response.status_code == 403:
                raise ProviderError(
                    "This OpenCode key cannot read Go usage. Create a restricted key with "
                    "Models: Request and Usage: Read.",
                    status=403,
                )
            raise self._error_from_response(response)
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as error:
            raise ProviderError("OpenCode returned an invalid Go usage response.") from error
        return _normalize_go_usage(payload)

    # ----------------------------------------------------------------- streaming

    async def stream(self, request: TurnRequest) -> AsyncIterator[StreamChunk]:
        # Fail fast on a missing key rather than after a catalogue lookup.
        if not self.api_key:
            self._headers(request.session_id)

        model_id = request.model or self.default_model
        family = await self.model_family(model_id)

        if family == "messages":
            async for chunk in self._stream_anthropic(request, model_id):
                yield chunk
        else:
            async for chunk in self._stream_chat_completions(request, model_id):
                yield chunk

    async def _stream_chat_completions(
        self, request: TurnRequest, model_id: str
    ) -> AsyncIterator[StreamChunk]:
        body: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "system", "content": request.system}, *request.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        url = f"{self.base_url}/openai/v1/chat/completions"

        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", url, json=body, headers=self._headers(request.session_id)
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise self._error_from_response(response)

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    for choice in event.get("choices", []):
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            yield StreamChunk(delta=delta)

                    usage = event.get("usage")
                    if usage:
                        yield StreamChunk(usage=_usage_from_openai(usage))

    async def _stream_anthropic(
        self, request: TurnRequest, model_id: str
    ) -> AsyncIterator[StreamChunk]:
        body: dict[str, Any] = {
            "model": model_id,
            "system": request.system,
            "messages": request.messages,
            "stream": True,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        url = f"{self.base_url}/anthropic/v1/messages"

        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", url, json=body, headers=self._headers(request.session_id)
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise self._error_from_response(response)

                usage: Usage = Usage()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = (event.get("delta") or {}).get("text")
                        if delta:
                            yield StreamChunk(delta=delta)
                    elif event_type == "message_start":
                        usage = _usage_from_anthropic(event.get("message") or {})
                    elif event_type == "message_delta":
                        usage = _merge_usage(usage, event.get("usage") or {})

                if usage.input_tokens or usage.output_tokens or usage.cost_usd is not None:
                    yield StreamChunk(usage=usage)

    # -------------------------------------------------------------------- errors

    def _error_from_response(self, response: httpx.Response) -> ProviderError:
        status = response.status_code
        detail = ""
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                detail = str(error.get("message") or "")
            elif isinstance(error, str):
                detail = error
            elif isinstance(payload, dict):
                detail = str(payload.get("detail") or payload.get("message") or "")
        except (json.JSONDecodeError, ValueError):
            detail = response.text[:200]

        if status in (401, 403):
            return ProviderError(
                "OpenCode rejected the request ("
                f"{status}). Check the API key and whether this model is available on your "
                f"Go plan. {detail}".strip(),
                status=status,
            )
        if status == 404:
            return ProviderError(
                f"OpenCode does not know the model '{response.request.url.path}'. "
                "Pick another model in Settings.",
                status=status,
            )
        if status == 429:
            return ProviderError(
                "Your OpenCode Go usage limit is exhausted. Wait for the next period or "
                f"change plans in the OpenCode Console. {detail}".strip(),
                status=status,
                retryable=True,
            )
        if status >= 500:
            return ProviderError(
                f"OpenCode is having trouble right now ({status}). Try again shortly. "
                f"{detail}".strip(),
                status=status,
                retryable=True,
            )
        return ProviderError(f"OpenCode request failed ({status}). {detail}".strip(), status=status)


def _normalize_go_usage(payload: dict) -> dict:
    """Normalize OpenCode's Go usage response into remaining percentages."""
    usage = payload.get("usage") if isinstance(payload, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    windows = {}
    for name in ("rolling", "weekly", "monthly"):
        meter = usage.get(name)
        if not isinstance(meter, dict):
            continue
        percent = float(meter.get("percent") or 0)
        windows[name] = {
            "used_percent": round(max(0.0, min(100.0, percent)), 1),
            "remaining_percent": round(max(0.0, min(100.0, 100.0 - percent)), 1),
            "limited": meter.get("status") == "rate-limited",
            "resets_at": meter.get("resetsAt"),
        }
    return {"windows": windows}


def _family_of(entry: dict) -> str:
    """Which wire format a catalogue entry uses."""
    api = entry.get("api") or {}
    if "messages" in api:
        return "messages"
    if "chat-completions" in api:
        return "chat-completions"
    if "responses" in api:
        return "responses"
    return "chat-completions"


def _is_free(entry: dict) -> bool:
    cost = ((entry.get("cost") or {}).get("text") or {})
    prices = [cost.get("input", {}).get("price"), cost.get("output", {}).get("price")]
    return bool(prices) and all(price == 0 for price in prices)


def _usage_from_openai(usage: dict) -> Usage:
    opencode = usage.get("opencode") or {}
    return Usage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=_maybe_float(usage.get("cost")),
        allowance_usd=_maybe_float(opencode.get("allowance")),
        billing_source=opencode.get("billing_source"),
    )


def _usage_from_anthropic(message: dict) -> Usage:
    opencode = message.get("opencode") or {}
    return Usage(
        input_tokens=int(message.get("input_tokens") or 0),
        output_tokens=int(message.get("output_tokens") or 0),
        cost_usd=_maybe_float(message.get("cost") or opencode.get("cost")),
        allowance_usd=_maybe_float(opencode.get("allowance")),
        billing_source=opencode.get("billing_source"),
    )


def _merge_usage(usage: Usage, update: dict) -> Usage:
    opencode = update.get("opencode") or {}
    return Usage(
        input_tokens=usage.input_tokens or int(update.get("input_tokens") or 0),
        output_tokens=int(update.get("output_tokens") or usage.output_tokens),
        cost_usd=(
            _maybe_float(update.get("cost"))
            if update.get("cost") is not None
            else usage.cost_usd
        ),
        allowance_usd=(
            _maybe_float(opencode.get("allowance"))
            if opencode.get("allowance") is not None
            else usage.allowance_usd
        ),
        billing_source=opencode.get("billing_source") or usage.billing_source,
    )


def _maybe_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
