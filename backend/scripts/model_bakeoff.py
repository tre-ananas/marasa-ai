"""Model bake-off: compare candidate models on a fixed prompt set.

Runs the real Marasa tutor prompt against each model and records the numbers
that decide the default: latency, throughput, whether the model honours the
`<marasa_notes>` contract, whether it replies in the target language, and the
reply itself for a qualitative read.

    uv run python scripts/model_bakeoff.py --models qwen3:8b,qwen3:4b
    uv run python scripts/model_bakeoff.py --models qwen3:4b --output docs/model-eval.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# Allow running the script directly: `uv run python scripts/model_bakeoff.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tutor.languages import resolve_language  # noqa: E402
from app.tutor.notes import parse_notes  # noqa: E402
from app.tutor.prompts import build_system_prompt  # noqa: E402
from app.tutor.tones import resolve_tone  # noqa: E402


@dataclass
class Scenario:
    name: str
    language: str
    tone: str
    level: str
    topic: str
    learner: str
    expect: str
    vocab: list[str] = field(default_factory=list)


SCENARIOS: list[Scenario] = [
    Scenario(
        name="Spanish · conversation",
        language="es",
        tone="conversation_partner",
        level="IM",
        topic="la comida italiana",
        learner="Me encanta la pasta carbonara, pero no me sale bien el italiano.",
        expect="replies in Spanish, asks one question, notes the learner's vocabulary",
    ),
    Scenario(
        name="Swedish · conversation",
        language="sv",
        tone="conversation_partner",
        level="IM",
        topic="svensk mat",
        learner="Jag gillar sillsallad, men jag kan inte laga pannbiff.",
        expect="replies in Swedish, asks one question",
    ),
    Scenario(
        name="Levantine Arabic · conversation",
        language="ar-lev",
        tone="conversation_partner",
        level="IM",
        topic="العائلة",
        learner="بحب أكل مع اهلي و特別اً جدتي.",
        expect="replies in colloquial Levantine Arabic, not MSA",
    ),
    Scenario(
        name="Spanish · formal interview",
        language="es",
        tone="formal_interview",
        level="AH",
        topic="una entrevista de trabajo",
        learner="Tengo cinco años de experiencia en atención al cliente.",
        expect="formal register, one structured question, no feedback",
    ),
    Scenario(
        name="Spanish · OPI examiner",
        language="es",
        tone="opi_examiner",
        level="IH",
        topic="experiencias de viaje",
        learner="El año pasado fui a Sevilla y me encantó la ciudad.",
        expect="acts like an examiner: no feedback, probes for the next level",
    ),
    Scenario(
        name="Swedish · OPI examiner",
        language="sv",
        tone="opi_examiner",
        level="IH",
        topic="arbete och utbildning",
        learner="Jag jobbar som sjuksköterska och studerar på kvällarna.",
        expect="acts like an examiner: no feedback, probes for the next level",
    ),
]

ARABIC = re.compile(r"[؀-ۿ]")
SPANISH = re.compile(r"[áéíóúüñ¿¡ÁÉÍÓÚÑ]")
SWEDISH = re.compile(r"[åäöÅÄÖ]")

SCRIPT_CHECK = {
    "es": SPANISH,
    "sv": SWEDISH,
    "ar-lev": ARABIC,
}


def looks_like(text: str, language: str) -> bool:
    if language == "auto":
        return True
    pattern = SCRIPT_CHECK.get(language)
    if pattern is None:
        return True
    # A short reply can be pure ASCII (e.g. "Claro."), so only judge when
    # there is enough text to be meaningful.
    return bool(pattern.search(text)) or len(text.split()) < 6


async def run_model(model: str, scenario: Scenario, host: str) -> dict:
    language = resolve_language(scenario.language)
    tone = resolve_tone(scenario.tone)
    system = build_system_prompt(
        language=language,
        tone=tone,
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
    started = time.perf_counter()
    first_token: float | None = None
    eval_count = 0
    prompt_tokens = 0

    async with httpx.AsyncClient(timeout=600) as client:
        async with client.stream("POST", f"{host}/api/chat", json=body) as response:
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
                    if first_token is None:
                        first_token = time.perf_counter() - started
                    chunks.append(delta)
                if event.get("done"):
                    eval_count = int(event.get("eval_count") or 0)
                    prompt_tokens = int(event.get("prompt_eval_count") or 0)

    total = time.perf_counter() - started
    raw = "".join(chunks)
    reply, notes = parse_notes(raw)

    generation = max((first_token or total), 0.001)
    return {
        "model": model,
        "scenario": scenario.name,
        "ttft": round(first_token or total, 2),
        "total_s": round(total, 2),
        "tok_per_s": round(eval_count / max(total - (first_token or total), 0.001), 1) if eval_count else 0,
        "prompt_tokens": prompt_tokens,
        "output_tokens": eval_count,
        "contract_ok": notes.parsed,
        "reply_chars": len(reply),
        "reply_words": len(reply.split()),
        "in_language": looks_like(reply, scenario.language),
        "vocab_notes": len(notes.vocab),
        "grammar_notes": len(notes.grammar),
        "reply": reply.strip(),
        "notes": {
            "vocab": [vars(note) for note in notes.vocab],
            "grammar": [vars(note) for note in notes.grammar],
            "level_delta": notes.level_delta,
            "next_step": notes.next_step,
        },
    }


def render_report(results: list[dict], scenarios: list[Scenario]) -> str:
    lines = ["# Model bake-off", ""]
    lines.append("Generated by `backend/scripts/model_bakeoff.py`. Same prompt, same order, same seed-free")
    lines.append("sampling (temperature 0.8) for every model.")
    lines.append("")

    models = list(dict.fromkeys(result["model"] for result in results))
    lines.append("## Summary")
    lines.append("")
    lines.append("| Model | Contract | In language | Avg TTFT | Avg total | Avg tok/s | Avg reply words |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for model in models:
        rows = [result for result in results if result["model"] == model]
        contract = sum(1 for row in rows if row["contract_ok"])
        language = sum(1 for row in rows if row["in_language"])
        ttft = sum(row["ttft"] for row in rows) / len(rows)
        total = sum(row["total_s"] for row in rows) / len(rows)
        speed = sum(row["tok_per_s"] for row in rows) / len(rows)
        words = sum(row["reply_words"] for row in rows) / len(rows)
        lines.append(
            f"| `{model}` | {contract}/{len(rows)} | {language}/{len(rows)} | "
            f"{ttft:.1f}s | {total:.1f}s | {speed:.1f} | {words:.0f} |"
        )
    lines.append("")

    lines.append("## Per scenario")
    lines.append("")
    for scenario in scenarios:
        lines.append(f"### {scenario.name}")
        lines.append("")
        lines.append(f"*Expectation:* {scenario.expect}")
        lines.append("")
        for model in models:
            row = next(
                (
                    result
                    for result in results
                    if result["model"] == model and result["scenario"] == scenario.name
                ),
                None,
            )
            if not row:
                continue
            lines.append(
                f"**`{model}`** — {row['total_s']}s, {row['output_tokens']} tokens, "
                f"contract {'ok' if row['contract_ok'] else 'FAILED'}, "
                f"{row['reply_words']} words"
            )
            lines.append("")
            lines.append(f"> {row['reply'] or '*(no reply)*'}")
            lines.append("")
            if row["notes"]["next_step"]:
                lines.append(f"*next step:* {row['notes']['next_step']}")
                lines.append("")
            if row["notes"]["vocab"]:
                pairs = ", ".join(
                    f"{note['term']} ({note['status']})" for note in row["notes"]["vocab"]
                )
                lines.append(f"*vocabulary:* {pairs}")
                lines.append("")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="qwen3:8b", help="comma-separated model ids")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    models = [model.strip() for model in args.models.split(",") if model.strip()]
    results: list[dict] = []

    for model in models:
        print(f"=== {model} ===", flush=True)
        for scenario in SCENARIOS:
            row = await run_model(model, scenario, args.host)
            results.append(row)
            print(
                f"  {scenario.name:38} {row['total_s']:6.1f}s  "
                f"ttft {row['ttft']:5.1f}s  {row['tok_per_s']:5.1f} tok/s  "
                f"contract={'ok' if row['contract_ok'] else 'FAIL'}  "
                f"lang={'ok' if row['in_language'] else 'CHECK'}  "
                f"{row['reply_words']:3d} words",
                flush=True,
            )

    report = render_report(results, SCENARIOS)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        print(f"\nwrote {path}")
    else:
        print("\n" + report)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
