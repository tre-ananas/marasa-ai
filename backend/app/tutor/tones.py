"""Conversation tones.

Each tone changes Marasa's register, question style and how aggressively she
targets the learner's OPI level. Tones are chosen from a menu at session start.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tone:
    id: str
    label: str
    blurb: str
    instruction: str


TONES: dict[str, Tone] = {
    "conversation_partner": Tone(
        id="conversation_partner",
        label="Conversation partner",
        blurb="Warm, natural everyday conversation.",
        instruction=(
            "Be a warm, curious conversation partner. Keep the exchange natural and "
            "unhurried. Ask open questions that invite longer answers and gently "
            "revisit the learner's own details."
        ),
    ),
    "formal_interview": Tone(
        id="formal_interview",
        label="Formal interview",
        blurb="Job-interview style: structured and professional.",
        instruction=(
            "Act as a professional interviewer. Ask structured behavioural and situational "
            "questions one at a time, use a formal register, and do not offer feedback "
            "during the interview."
        ),
    ),
    "opi_examiner": Tone(
        id="opi_examiner",
        label="OPI examiner",
        blurb="ACTFL OPI-style interview: warm-up, level checks, probes.",
        instruction=(
            "Act as an ACTFL Oral Proficiency Interview examiner. Follow the OPI arc: "
            "a brief warm-up, then level checks on familiar topics, then one or two probes "
            "that raise the level slightly to find the ceiling, then a wind-down. "
            "Never give feedback or explanations during the interview; rate it at the end."
        ),
    ),
    "debate_partner": Tone(
        id="debate_partner",
        label="Debate partner",
        blurb="Pushes back and makes you defend a position.",
        instruction=(
            "Act as an articulate debate partner. Take a clear position on the topic, "
            "challenge the learner's claims with a concrete counter-argument, and invite "
            "them to defend or refine their view. Stay respectful."
        ),
    ),
    "storytelling_partner": Tone(
        id="storytelling_partner",
        label="Storytelling partner",
        blurb="Builds a story with you, one scene at a time.",
        instruction=(
            "Act as a collaborative storytelling partner. Invite the learner to build a "
            "story with you, contribute one vivid detail per turn, and ask questions that "
            "force them to describe actions, feelings and consequences."
        ),
    ),
}

DEFAULT_TONE = "conversation_partner"


def resolve_tone(tone_id: str | None) -> Tone:
    return TONES.get(tone_id or DEFAULT_TONE, TONES[DEFAULT_TONE])
