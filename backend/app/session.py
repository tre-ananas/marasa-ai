"""In-memory session store.

Deliberately ephemeral: transcripts, observations and assessments live only as
long as the app is running. Nothing is written to disk, so closing Marasa
erases the session. The learner's only durable artefact is the PDF they
download (README: "Minimal Viable Product").

Rules:
- each signed-in browser owns its own active session;
- sessions are ephemeral and disappear when Marasa closes;
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
    """Retained for compatibility with callers that expect this error type."""


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    @property
    def active(self) -> Session | None:
        """The most recently created active session."""
        if not self._sessions:
            return None
        return next(reversed(self._sessions.values()))

    def create(self, **kwargs) -> Session:
        session = Session(id=uuid.uuid4().hex, **kwargs)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def discard(self, session_id: str | None = None) -> bool:
        if session_id:
            return self._sessions.pop(session_id, None) is not None
        if not self._sessions:
            return False
        self._sessions.pop(next(reversed(self._sessions)))
        return True

    def clear(self) -> None:
        self._sessions.clear()


store = SessionStore()
