"""Target languages supported by the MVP.

The UI language is English only. Target languages define the conversation
language, the speech-recognition locale and the dialect instruction that is
injected into the tutor prompt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    id: str
    label: str
    stt_locale: str
    dialect_note: str = ""


LANGUAGES: dict[str, Language] = {
    "auto": Language(
        id="auto",
        label="Auto (infer from my first message)",
        stt_locale="",
        dialect_note="Infer the target language from the learner's first message.",
    ),
    "es": Language(
        id="es",
        label="Spanish",
        stt_locale="es-ES",
        dialect_note="Use neutral Latin American Spanish unless the learner sets a variety.",
    ),
    "ar-lev": Language(
        id="ar-lev",
        label="Levantine Arabic (colloquial)",
        stt_locale="ar-SY",
        dialect_note=(
            "Speak Levantine colloquial Arabic (شامي), not Modern Standard Arabic. "
            "Use everyday dialect vocabulary, natural word order and dialect particles. "
            "Do not translate the learner's dialect into MSA."
        ),
    ),
    "sv": Language(
        id="sv",
        label="Swedish",
        stt_locale="sv-SE",
        dialect_note="Use standard Swedish (svenska).",
    ),
}

DEFAULT_LANGUAGE = "auto"


def resolve_language(language_id: str | None) -> Language:
    return LANGUAGES.get(language_id or DEFAULT_LANGUAGE, LANGUAGES[DEFAULT_LANGUAGE])


# Used when a model answers with the machine-readable block only, so the
# learner would otherwise see an empty bubble.
CONTINUATION_FALLBACK: dict[str, str] = {
    "es": "¿Sobre qué te gustaría seguir hablando?",
    "sv": "Vad vill du öva nu?",
    "ar-lev": "شو بدك تكمّل عليه؟",
    "auto": "What would you like to talk about next?",
}


def continuation_fallback(language_id: str | None) -> str:
    return CONTINUATION_FALLBACK.get(language_id or "auto", CONTINUATION_FALLBACK["auto"])
