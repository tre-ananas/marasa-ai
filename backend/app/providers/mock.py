"""Offline provider used by default, by tests, and for UI work with no key.

It emits a plausible reply plus a well-formed ``<marasa_notes>`` block so the
whole pipeline (streaming, note parsing, recap rendering) can be exercised
without spending tokens.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .base import ModelInfo, StreamChunk, TurnRequest, Usage

_REPLIES: dict[str, str] = {
    "es": (
        "Qué interesante, cuéntame más de ese tema. "
        "¿Qué fue lo que te hizo decidir hacerlo?"
    ),
    "sv": (
        "Det låter intressant, berätta mer om hur det gick. "
        "Vad tänkte du när du bestämde dig för att göra det?"
    ),
    "ar-lev": (
        "موضوع كتير ممتع، حكيني أكتر عنه. "
        "شو السبب اللي خلاك تاخذ هالقرار؟"
    ),
    "auto": (
        "That sounds interesting — tell me more about it. "
        "What made you decide to go that way?"
    ),
}


class MockProvider:
    name = "mock"
    default_model = "mock-chat"

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id="mock-chat",
                label="Mock (offline)",
                free=True,
                notes="Deterministic offline replies for tests and UI development.",
            )
        ]

    async def stream(self, request: TurnRequest) -> AsyncIterator[StreamChunk]:
        language = "auto"
        for message in reversed(request.messages):
            if message.get("role") == "user":
                language = _detect_language(message.get("content", ""))
                break

        reply = _REPLIES.get(language, _REPLIES["auto"])
        notes = {
            "vocab": [
                {
                    "term": "decision",
                    "meaning": "a choice made after thinking",
                    "status": "useful",
                    "evidence": "decide",
                }
            ],
            "grammar": [
                {
                    "concept": "past tense narration",
                    "status": "gap",
                    "note": "Keep aspect markers consistent when narrating.",
                }
            ],
            "level_delta": {"grammar": 0, "vocab": 0, "discourse": 0},
            "next_step": "Try answering with a full paragraph next time.",
        }

        payload = f"{reply}\n\n<marasa_notes>\n{json.dumps(notes, ensure_ascii=False)}\n</marasa_notes>"
        for token in _tokenize(payload):
            await asyncio.sleep(0.01)
            yield StreamChunk(delta=token)

        yield StreamChunk(
            usage=Usage(
                input_tokens=len(request.system) // 4,
                output_tokens=len(payload) // 4,
                cost_usd=0.0,
                billing_source="free",
            )
        )


def _detect_language(text: str) -> str:
    """Very rough script/stop-word scoring for the offline mock provider."""
    lowered = f" {text.lower()} "
    if any(char in text for char in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"):
        return "ar-lev"

    markers = {
        "es": (" que ", " quiero ", " me ", " mi ", " la ", " el ", " y ", " una ", " con ",
               " para ", " gracias ", " mucho ", " encanta "),
        "sv": (" och ", " jag ", " inte ", " det ", " med ", " för ", " att ", " på ", " gillar ",
               " du ", " mig ", " kan "),
        "en": (" the ", " what ", " how ", " why ", " and ", " tell ", " about ", " you "),
    }
    scores = {code: sum(1 for marker in words if marker in lowered) for code, words in markers.items()}
    best = max(scores, key=lambda code: scores[code])
    return best if scores[best] > 0 else "auto"


def _tokenize(text: str) -> list[str]:
    return [text[index : index + 12] for index in range(0, len(text), 12)]
