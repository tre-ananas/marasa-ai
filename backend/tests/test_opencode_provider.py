import json

import httpx
import pytest
import respx

from app.providers.base import TurnRequest
from app.providers.opencode_console import OpenCodeConsoleProvider, ProviderError

BASE = "https://opencode.ai/inference/go"
CHAT = f"{BASE}/openai/v1/chat/completions"
MESSAGES = f"{BASE}/anthropic/v1/messages"
MODELS = f"{BASE}/v1/models"

CATALOGUE = {
    "data": [
        {
            "id": "minimax-m3",
            "name": "MiniMax M3",
            "limit": {"context": 1000000},
            "cost": {"text": {"input": {"price": 0.30}, "output": {"price": 1.20}}},
            "api": {"messages": {"base_url": f"{BASE}/anthropic/v1"}},
        },
        {
            "id": "qwen3.8-flash",
            "name": "Qwen3.8 Flash",
            "limit": {"context": 1000000},
            "cost": {"text": {"input": {"price": 0.15}, "output": {"price": 0.47}}},
            "api": {"chat-completions": {"base_url": f"{BASE}/openai/v1"}},
        },
    ]
}


def _provider(api_key: str = "sk-test") -> OpenCodeConsoleProvider:
    return OpenCodeConsoleProvider(api_key=api_key, endpoint="go")


def _request(model: str = "minimax-m3") -> TurnRequest:
    return TurnRequest(
        session_id="session-123",
        system="system prompt",
        messages=[{"role": "user", "content": "hola"}],
        model=model,
    )


@pytest.mark.asyncio
@respx.mock
async def test_lists_models_and_marks_the_free_ones() -> None:
    respx.get(MODELS).mock(return_value=httpx.Response(200, json=CATALOGUE))

    models = await _provider().list_models()
    by_id = {model.id: model for model in models}
    assert by_id["minimax-m3"].free is False
    assert by_id["minimax-m3"].endpoint == "messages"
    assert by_id["qwen3.8-flash"].free is False
    assert by_id["qwen3.8-flash"].endpoint == "chat-completions"


@pytest.mark.asyncio
@respx.mock
async def test_streams_chat_completions_with_cost_and_allowance() -> None:
    respx.get(MODELS).mock(return_value=httpx.Response(200, json=CATALOGUE))
    route = respx.post(CHAT).mock(
        return_value=httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"Hola"}}]}\n'
                'data: {"choices":[{"delta":{"content":", ¿qué tal?"}}]}\n'
                'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":120,"completion_tokens":45,'
                '"cost":0.00042,"opencode":{"billing_source":"go","allowance":0.00042}}}\n'
                "data: [DONE]\n"
            ),
        )
    )

    chunks = [chunk async for chunk in _provider().stream(_request("qwen3.8-flash"))]

    assert "".join(chunk.delta for chunk in chunks) == "Hola, ¿qué tal?"
    usage = chunks[-1].usage
    assert usage is not None
    assert usage.input_tokens == 120
    assert usage.output_tokens == 45
    assert usage.cost_usd == 0.00042
    assert usage.allowance_usd == 0.00042
    assert usage.billing_source == "go"

    headers = route.calls[0].request.headers
    assert headers["Authorization"] == "Bearer sk-test"
    # OpenCode attributes Go usage using a stable session id.
    assert headers["x-opencode-session"] == "session-123"
    assert "marasa-ai" in headers["User-Agent"]


@pytest.mark.asyncio
@respx.mock
async def test_streams_anthropic_messages_family() -> None:
    respx.get(MODELS).mock(return_value=httpx.Response(200, json=CATALOGUE))
    route = respx.post(MESSAGES).mock(
        return_value=httpx.Response(
            200,
            text=(
                'data: {"type":"message_start","message":{"input_tokens":88,"output_tokens":0,'
                '"opencode":{"billing_source":"go"}}}\n'
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Buongiorno"}}\n'
                'data: {"type":"message_delta","usage":{"output_tokens":12,"cost":0.0001}}\n'
            ),
        )
    )

    chunks = [chunk async for chunk in _provider().stream(_request("minimax-m3"))]

    assert "".join(chunk.delta for chunk in chunks) == "Buongiorno"
    usage = chunks[-1].usage
    assert usage is not None
    assert usage.input_tokens == 88
    assert usage.output_tokens == 12
    assert usage.cost_usd == 0.0001
    assert route.calls[0].request.headers["x-opencode-session"] == "session-123"


@pytest.mark.asyncio
@respx.mock
async def test_missing_key_is_reported_clearly() -> None:
    provider = OpenCodeConsoleProvider(api_key=None, endpoint="go")
    provider.api_key = None
    with pytest.raises(ProviderError) as error:
        async for _ in provider.stream(_request()):
            pass
    assert "API key" in str(error.value)


@pytest.mark.asyncio
@respx.mock
async def test_quota_error_mentions_the_limit() -> None:
    respx.get(MODELS).mock(return_value=httpx.Response(200, json=CATALOGUE))
    respx.post(MESSAGES).mock(
        return_value=httpx.Response(429, json={"error": {"message": "allowance exhausted"}})
    )

    with pytest.raises(ProviderError) as error:
        async for _ in _provider().stream(_request()):
            pass
    assert error.value.status == 429
    assert "limit" in str(error.value).lower() or "balance" in str(error.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_unauthorized_error_is_reported() -> None:
    respx.get(MODELS).mock(return_value=httpx.Response(200, json=CATALOGUE))
    respx.post(MESSAGES).mock(
        return_value=httpx.Response(401, json={"error": {"message": "invalid key"}})
    )

    with pytest.raises(ProviderError) as error:
        async for _ in _provider().stream(_request()):
            pass
    assert error.value.status == 401
    assert "API key" in str(error.value)
