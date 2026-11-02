import json

import httpx
import pytest
import respx

from app.providers.base import TurnRequest
from app.providers.ollama import OllamaProvider

OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"


@pytest.mark.asyncio
@respx.mock
async def test_ollama_streams_content_then_usage() -> None:
    route = respx.post(OLLAMA_CHAT).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"message":{"content":"Hej"},"done":false}\n'
                '{"message":{"content":"!"},"done":false}\n'
                '{"done":true,"prompt_eval_count":120,"eval_count":42}\n'
            ),
        )
    )

    provider = OllamaProvider()
    chunks = [
        chunk
        async for chunk in provider.stream(
            TurnRequest(
                session_id="s1",
                system="system prompt",
                messages=[{"role": "user", "content": "hej"}],
                model="qwen3:8b",
            )
        )
    ]

    assert "".join(chunk.delta for chunk in chunks) == "Hej!"
    usage = chunks[-1].usage
    assert usage is not None
    assert usage.input_tokens == 120
    assert usage.output_tokens == 42
    assert usage.cost_usd == 0.0
    assert usage.billing_source == "local"

    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "qwen3:8b"
    assert body["messages"][0]["role"] == "system"
    # The thinking mode would burn tokens on output the adapter discards.
    assert body["think"] is False
    # Ollama defaults to a 4K context, too small for the tutor prompt.
    assert body["options"]["num_ctx"] == 8192


@pytest.mark.asyncio
@respx.mock
async def test_ollama_lists_local_models() -> None:
    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen3:8b", "size": 5200000000, "details": {"parameter_size": "8.2B"}}
                ]
            },
        )
    )

    models = await OllamaProvider().list_models()
    assert [model.id for model in models] == ["qwen3:8b"]
    assert models[0].free is True


@pytest.mark.asyncio
@respx.mock
async def test_ollama_reports_connection_failure() -> None:
    respx.post(OLLAMA_CHAT).mock(side_effect=httpx.ConnectError("connection refused"))

    provider = OllamaProvider()
    with pytest.raises(httpx.ConnectError):
        async for _ in provider.stream(
            TurnRequest(session_id="s", system="s", messages=[{"role": "user", "content": "x"}], model="qwen3:8b")
        ):
            pass
