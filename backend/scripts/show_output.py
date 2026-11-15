"""Show the raw output of one scenario for a given model (debugging aid)."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_bakeoff import SCENARIOS  # noqa: E402
from app.tutor.languages import resolve_language  # noqa: E402
from app.tutor.prompts import build_system_prompt  # noqa: E402
from app.tutor.tones import resolve_tone  # noqa: E402


async def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:4b"
    index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    scenario = SCENARIOS[index]

    system = build_system_prompt(
        language=resolve_language(scenario.language),
        tone=resolve_tone(scenario.tone),
        level=scenario.level,
        target_level=scenario.level,
        topics=[scenario.topic],
        vocab_terms=scenario.vocab,
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": scenario.learner},
        ],
        "stream": True,
        "think": False,
        "options": {"temperature": 0.8, "num_predict": 900, "num_ctx": 8192},
    }

    chunks: list[str] = []
    async with httpx.AsyncClient(timeout=600) as client:
        async with client.stream("POST", "http://127.0.0.1:11434/api/chat", json=body) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = (event.get("message") or {}).get("content", "")
                if delta:
                    chunks.append(delta)

    raw = "".join(chunks)
    print(f"--- {model} / {scenario.name}: {len(raw)} chars, {len(raw.split())} words ---")
    print(raw[:2500])
    print("...")
    print(raw[-600:])


asyncio.run(main())
