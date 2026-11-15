"""Ephemeral OpenCode Go sign-in sessions.

The supported OpenCode Go integration uses a personal API key. Marasa keeps
that key only in process memory for the lifetime of the browser session: it is
never written to ``settings.json``, never returned by an API response, and is
cleared when the session is ended or the server restarts.

The browser receives an opaque, signed session token in an HttpOnly cookie.
Only the token's digest is used as the lookup key, so a captured token cannot
be used to retrieve the API key from the store.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from threading import RLock

from fastapi import HTTPException, Request, Response, status

SESSION_COOKIE = "marasa_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
_TOKEN_BYTES = 32


@dataclass(frozen=True)
class AuthSession:
    """A signed-in browser session and its OpenCode Go credential."""

    token_digest: str
    api_key: str
    created_at: int
    expires_at: int
    model: str = ""

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


@dataclass
class _SessionState:
    session: AuthSession
    learning_session_id: str | None = None
    metadata: dict = field(default_factory=dict)


class AuthSessionStore:
    """In-memory, process-local sessions containing OpenCode credentials."""

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionState] = {}
        self._lock = RLock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, api_key: str, model: str = "") -> tuple[str, AuthSession]:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        now = int(time.time())
        session = AuthSession(
            token_digest=self._digest(token),
            api_key=api_key,
            created_at=now,
            expires_at=now + SESSION_TTL_SECONDS,
            model=model,
        )
        with self._lock:
            self._prune(now)
            self._sessions[session.token_digest] = _SessionState(session=session)
        return token, session

    def get(self, token: str | None) -> AuthSession | None:
        if not token:
            return None
        digest = self._digest(token)
        now = int(time.time())
        with self._lock:
            self._prune(now)
            state = self._sessions.get(digest)
            return state.session if state else None

    def get_state(self, token: str | None) -> _SessionState | None:
        if not token:
            return None
        digest = self._digest(token)
        now = int(time.time())
        with self._lock:
            self._prune(now)
            return self._sessions.get(digest)

    def bind_learning_session(self, token: str, learning_session_id: str) -> None:
        digest = self._digest(token)
        with self._lock:
            state = self._sessions.get(digest)
            if state:
                state.learning_session_id = learning_session_id

    def unbind_learning_session(self, token: str, learning_session_id: str) -> None:
        digest = self._digest(token)
        with self._lock:
            state = self._sessions.get(digest)
            if state and state.learning_session_id == learning_session_id:
                state.learning_session_id = None

    def rotate(self, token: str, api_key: str, model: str = "") -> str | None:
        """Issue a fresh browser token for an existing sign-in session."""
        digest = self._digest(token)
        now = int(time.time())
        with self._lock:
            self._prune(now)
            state = self._sessions.get(digest)
            if state is None:
                return None
            new_token = secrets.token_urlsafe(_TOKEN_BYTES)
            new_session = AuthSession(
                token_digest=self._digest(new_token),
                api_key=api_key,
                created_at=state.session.created_at,
                expires_at=state.session.expires_at,
                model=model or state.session.model,
            )
            self._sessions.pop(digest, None)
            self._sessions[new_session.token_digest] = _SessionState(
                session=new_session,
                learning_session_id=state.learning_session_id,
                metadata=state.metadata,
            )
            return new_token

    def delete(self, token: str | None) -> bool:
        if not token:
            return False
        digest = self._digest(token)
        with self._lock:
            return self._sessions.pop(digest, None) is not None

    def _prune(self, now: int) -> None:
        expired = [digest for digest, state in self._sessions.items() if state.session.expired]
        for digest in expired:
            self._sessions.pop(digest, None)


auth_store = AuthSessionStore()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )


def rotate_session_cookie(response: Response, token: str) -> None:
    """Replace the browser token while preserving the same expiry policy."""
    set_session_cookie(response, token)


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="strict")


def require_session(request: Request) -> AuthSession:
    session = auth_store.get(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with OpenCode Go to continue.",
            headers={"WWW-Authenticate": "Session"},
        )
    return session


def require_owned_learning_session(request: Request, session_id: str) -> AuthSession:
    """Require a sign-in and ensure it owns the requested learning session."""
    auth_session = require_session(request)
    state = auth_store.get_state(request.cookies.get(SESSION_COOKIE))
    if state is None or state.learning_session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return auth_session


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
