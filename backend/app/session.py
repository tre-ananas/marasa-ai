"""In-memory session store.

Deliberately ephemeral: transcripts, observations and assessments live only as
long as the app is running. Nothing is written to disk, so closing Marasa
erases the session. The learner's only durable artefact is the PDF they
download (README: "Minimal Viable Product").

Rules:
- exactly one active session at a time;
- starting a new session requires discarding the current one;
- a new session is a new agent with no memory of previous discussions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Message:
    role: str
    content: str
    ts: str = field(default_factory=_now)
    meta: dict = field(default_factory=dict)


@dataclass
class Observation:
    kind: str  # 'vocab' | 'grammar'
    term: str
    status: str  # 'strong' | 'gap' | 'useful'
    meaning: str = ""
    note: str = ""
    evidence: str = ""
    ts: str = field(default_factory=_now)


@dataclass
class Session:
    id: str
    language_id: str
    tone_id: str
    mode: str  # 'text' | 'voice'
    topics: list[str] = field(default_factory=list)
    vocab_terms: list[str] = field(default_factory=list)
    level: str = "IM"
    target_level: str = "IM"
    provider: str = "mock"
    model: str = "mock-chat"
    status: str = "active"
    created_at: str = field(default_factory=_now)
    ended_at: str | None = None
    messages: list[Message] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str, **meta) -> Message:
        message = Message(role=role, content=content, meta=meta)
        self.messages.append(message)
        return message

    def add_observation(self, observation: Observation) -> None:
        self.observations.append(observation)


class ActiveSessionExists(RuntimeError):
    """Raised when a second session is started without discarding the first."""


class SessionStore:
    def __init__(self) -> None:
        self._active: Session | None = None

    @property
    def active(self) -> Session | None:
        return self._active

    def create(self, **kwargs) -> Session:
        if self._active is not None:
            raise ActiveSessionExists(
                "A session is already running. Download the recap PDF, then discard it "
                "before starting a new session."
            )
        session = Session(id=uuid.uuid4().hex, **kwargs)
        self._active = session
        return session

    def get(self, session_id: str) -> Session | None:
        if self._active and self._active.id == session_id:
            return self._active
        return None

    def discard(self, session_id: str | None = None) -> bool:
        if self._active is None:
            return False
        if session_id and self._active.id != session_id:
            return False
        self._active = None
        return True

    def clear(self) -> None:
        self._active = None


store = SessionStore()
