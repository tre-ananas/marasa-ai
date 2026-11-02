"""Parser for the tutor's structured note block.

The tutor answers with a conversational reply followed by a machine-readable
block:

    <reply>

    <marasa_notes>
    {"vocab": [...], "grammar": [...], "level_delta": {...}, "next_step": "..."}
    </marasa_notes>

Parsing is deliberately forgiving: a malformed block must never break a
conversation. When parsing fails the reply is still shown to the learner and
the notes are dropped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

NOTES_BLOCK = re.compile(r"<marasa_notes>\s*(.*?)\s*</marasa_notes>", re.DOTALL | re.IGNORECASE)

VALID_VOCAB_STATUS = {"strong", "gap", "useful"}
VALID_GRAMMAR_STATUS = {"strong", "gap"}


@dataclass
class VocabNote:
    term: str
    meaning: str = ""
    status: str = "useful"
    evidence: str = ""


@dataclass
class GrammarNote:
    concept: str
    status: str = "gap"
    note: str = ""


@dataclass
class Notes:
    vocab: list[VocabNote] = field(default_factory=list)
    grammar: list[GrammarNote] = field(default_factory=list)
    level_delta: dict[str, int] = field(default_factory=dict)
    next_step: str = ""
    parsed: bool = False


def _as_str(value: object, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _parse_notes_payload(payload: object) -> Notes:
    notes = Notes(parsed=True)
    if not isinstance(payload, dict):
        return Notes()

    vocab = payload.get("vocab")
    if isinstance(vocab, list):
        for item in vocab:
            if not isinstance(item, dict):
                continue
            term = _as_str(item.get("term"))
            if not term:
                continue
            status = _as_str(item.get("status"), "useful").lower()
            notes.vocab.append(
                VocabNote(
                    term=term,
                    meaning=_as_str(item.get("meaning")),
                    status=status if status in VALID_VOCAB_STATUS else "useful",
                    evidence=_as_str(item.get("evidence")),
                )
            )

    grammar = payload.get("grammar")
    if isinstance(grammar, list):
        for item in grammar:
            if not isinstance(item, dict):
                continue
            concept = _as_str(item.get("concept"))
            if not concept:
                continue
            status = _as_str(item.get("status"), "gap").lower()
            notes.grammar.append(
                GrammarNote(
                    concept=concept,
                    status=status if status in VALID_GRAMMAR_STATUS else "gap",
                    note=_as_str(item.get("note")),
                )
            )

    delta = payload.get("level_delta")
    if isinstance(delta, dict):
        notes.level_delta = {
            key: max(-1, min(1, _as_int(delta.get(key))))
            for key in ("grammar", "vocab", "discourse")
            if key in delta
        }

    notes.next_step = _as_str(payload.get("next_step"))
    return notes


def parse_notes(text: str) -> tuple[str, Notes]:
    """Split a raw model answer into ``(visible_reply, notes)``."""
    if not text:
        return "", Notes()

    match = NOTES_BLOCK.search(text)
    if not match:
        return text.strip(), Notes()

    visible = text[: match.start()].strip()
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return visible, Notes()

    return visible, _parse_notes_payload(payload)
