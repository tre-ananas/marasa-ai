"""ACTFL OPI level ladder.

Source of truth: the *ACTFL Oral Proficiency Interview Familiarization Guide
2020* (ACTFL, © 2020), which reproduces the ACTFL Proficiency Guidelines 2012
– Speaking. A copy is expected at ``OPI-Familiarization-Guide-2020-1.pdf`` in
the repo root (gitignored: the material is not redistributable).

The descriptors below are **paraphrased summaries** written for this project —
they are not verbatim reproductions. The structure follows the ACTFL rating
scale: four major levels (Novice, Intermediate, Advanced, Superior), with
Low/Mid/High sublevels for the first three, rated by the speaker's *floor*
(sustained performance) and *ceiling* (where performance breaks down).

An official OPI rating is only issued by ACTFL-certified testers; Marasa's
score is an estimate and must be labelled as one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    code: str
    label: str
    major: str
    summary: str
    text_type: str
    accuracy: str


LEVELS: tuple[Level, ...] = (
    Level(
        "NL",
        "Novice Low",
        "Novice",
        "No real functional ability; with time and familiar cues may exchange "
        "greetings, give a name, and name a few familiar objects.",
        "Isolated words and phrases",
        "May be unintelligible.",
    ),
    Level(
        "NM",
        "Novice Mid",
        "Novice",
        "Communicates minimally with memorized words and phrases; answers direct "
        "questions in two or three words; frequent pauses and recycling.",
        "Isolated words and memorized phrases",
        "Understood with difficulty, even by sympathetic listeners.",
    ),
    Level(
        "NH",
        "Novice High",
        "Novice",
        "Handles a variety of simple, everyday tasks but cannot sustain "
        "Intermediate-level discourse; leans on learned phrases and recombinations.",
        "Short, sometimes complete sentences (present tense)",
        "Often intelligible to sympathetic listeners; misunderstandings occur.",
    ),
    Level(
        "IL",
        "Intermediate Low",
        "Intermediate",
        "Handles a limited number of uncomplicated tasks in straightforward social "
        "situations; mostly reactive; struggles to link ideas or handle time and aspect.",
        "Short statements and discrete sentences",
        "Frequent misunderstandings; repetition often needed.",
    ),
    Level(
        "IM",
        "Intermediate Mid",
        "Intermediate",
        "Handles a variety of uncomplicated tasks in predictable social situations; "
        "can ask questions when needed; speaks in sentences and strings of sentences.",
        "Sentences and strings of sentences",
        "Generally understood by sympathetic listeners.",
    ),
    Level(
        "IH",
        "Intermediate High",
        "Intermediate",
        "Handles routine tasks with ease and confidence; can narrate in all major time "
        "frames in paragraph-length discourse, but not consistently.",
        "Connected paragraph-length discourse",
        "Understood by native speakers; some gaps or breakdowns.",
    ),
    Level(
        "AL",
        "Advanced Low",
        "Advanced",
        "Handles many communicative tasks in most informal and some formal settings; "
        "narrates and describes in the major time frames; performance is uneven and "
        "grammatically rough.",
        "Paragraph-length discourse",
        "Understood by native speakers, sometimes needing repetition.",
    ),
    Level(
        "AM",
        "Advanced Mid",
        "Advanced",
        "Handles a large number of tasks with ease and confidence on concrete topics; "
        "narrates and describes fully with good control of aspect; vocabulary is "
        "extensive but mostly generic.",
        "Connected, interwoven paragraph discourse",
        "Readily understood by native speakers.",
    ),
    Level(
        "AH",
        "Advanced High",
        "Advanced",
        "Performs all Advanced-level tasks with ease and confidence; handles some "
        "Superior-level tasks but cannot sustain them; can argue and hypothesise.",
        "Structured, extended discourse",
        "Understood without difficulty by native speakers.",
    ),
    Level(
        "S",
        "Superior",
        "Superior",
        "Participates fully in formal and informal discussion, concrete and abstract; "
        "explains complex matters, presents structured arguments, constructs "
        "hypotheses; no pattern of error in basic structures.",
        "Extended, tightly organised discourse",
        "Errors never interfere with communication.",
    ),
)

LEVEL_CODES: tuple[str, ...] = tuple(level.code for level in LEVELS)

# The OPI protocol assumes an Intermediate-level conversation to begin with.
DEFAULT_LEVEL = "IM"


def index_of(code: str) -> int:
    try:
        return LEVEL_CODES.index(code.upper())
    except ValueError:
        return LEVEL_CODES.index(DEFAULT_LEVEL)


def get_level(code: str) -> Level:
    return LEVELS[index_of(code)]


def clamp_delta(current: str, delta: int) -> str:
    """Move ``current`` by ``delta`` sublevels, staying inside the ladder."""
    if delta == 0:
        return current.upper()
    target = index_of(current) + (1 if delta > 0 else -1)
    target = max(0, min(len(LEVELS) - 1, target))
    return LEVEL_CODES[target]


def level_summary(code: str) -> str:
    level = get_level(code)
    return f"{level.label} ({level.code}) — {level.summary}"
