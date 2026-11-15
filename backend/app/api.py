"""HTTP API."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .auth import (
    SESSION_COOKIE,
    auth_store,
    clear_session_cookie,
    require_owned_learning_session,
    require_session,
    set_session_cookie,
)
from .config import (
    DEFAULT_MODEL,
    clear_stored_settings,
    get_settings,
)
from .providers.base import TurnRequest
from .providers.opencode_console import ProviderError
from .providers.registry import ProviderUnavailable, get_provider
from .session import ActiveSessionExists, Observation, Session, store
from .tutor.languages import LANGUAGES, continuation_fallback, resolve_language
from .tutor.notes import parse_notes
from .tutor.prompts import build_system_prompt
from .tutor.rubric import DEFAULT_LEVEL, clamp_delta
from .tutor.tones import TONES, resolve_tone

router = APIRouter(prefix="/api")


class SessionCreate(BaseModel):
    prompt: str = Field(default="", max_length=4000)
    language: str = "auto"
    tone: str = "conversation_partner"
    mode: str = "text"
    topics: list[str] = Field(default_factory=list)
    vocab_terms: list[str] = Field(default_factory=list)


class SessionCreateResponse(BaseModel):
    session_id: str
    language: str
    language_label: str
    tone: str
    tone_label: str
    mode: str
    topics: list[str]
    vocab_terms: list[str]
    level: str
    provider: str
    model: str


class DiscardResponse(BaseModel):
    discarded: bool


def _session_payload(session: Session) -> SessionCreateResponse:
    language = resolve_language(session.language_id)
    tone = resolve_tone(session.tone_id)
    return SessionCreateResponse(
        session_id=session.id,
        language=language.id,
        language_label=language.label,
        tone=tone.id,
        tone_label=tone.label,
        mode=session.mode,
        topics=session.topics,
        vocab_terms=session.vocab_terms,
        level=session.level,
        provider=session.provider,
        model=session.model,
    )


class SettingsUpdate(BaseModel):
    model: str | None = None


class ConnectionTest(BaseModel):
    model: str | None = None


class SignInRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    model = settings.model or DEFAULT_MODEL
    return {
        "ok": True,
        "app": settings.app_name,
        "provider": "console",
        "model": model,
        "authenticated": False,
        "endpoint": "go",
    }


@router.get("/settings")
async def read_settings(request: Request) -> dict:
    settings = get_settings()
    auth_session = auth_store.get(request.cookies.get(SESSION_COOKIE))
    return {
        "provider": "console",
        "model": auth_session.model if auth_session else "",
        "authenticated": auth_session is not None,
        "endpoint": "go",
        "free_model": DEFAULT_MODEL,
        "paid_model": DEFAULT_MODEL,
        "pdf_engine": settings.pdf_engine,
        "languages": [
            {"id": lang.id, "label": lang.label, "stt_locale": lang.stt_locale}
            for lang in LANGUAGES.values()
        ],
        "tones": [
            {"id": tone.id, "label": tone.label, "blurb": tone.blurb} for tone in TONES.values()
        ],
    }


@router.post("/auth/opencode/sign-in")
async def sign_in(payload: SignInRequest, response: Response) -> dict:
    """Create an ephemeral OpenCode Go session.

    OpenCode's documented third-party Go integration uses a personal API key.
    The key is retained only in memory and is never persisted or returned.
    """
    clear_stored_settings(get_settings().data_dir)
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Enter your OpenCode Go API key.")

    provider = get_provider("console", api_key=api_key)
    try:
        catalogue = await provider.list_models()
    except ProviderError as error:
        raise HTTPException(status_code=error.status or 502, detail=str(error)) from error
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="OpenCode did not respond in time.") from error

    model = DEFAULT_MODEL
    if not any(item.id == model for item in catalogue):
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{model}' is not available on your Go plan. Marasa uses only "
                f"{model}; check that your OpenCode workspace has Go access."
            ),
        )

    token, auth_session = auth_store.create(api_key, model=model)
    set_session_cookie(response, token)
    return {
        "authenticated": True,
        "endpoint": "go",
        "model": auth_session.model or DEFAULT_MODEL,
        "expires_at": auth_session.expires_at,
    }


@router.post("/auth/sign-out")
async def sign_out(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    auth_store.delete(token)
    clear_session_cookie(response)
    return {"authenticated": False}


@router.put("/settings")
async def update_settings(request: Request, payload: SettingsUpdate) -> dict:
    """Validate the request and return the fixed OpenCode Go settings."""
    require_session(request)
    return await read_settings(request)


@router.post("/auth/opencode/refresh")
async def refresh_sign_in(request: Request, response: Response) -> dict:
    """Rotate the local browser token without changing the Go credential."""
    token = request.cookies.get(SESSION_COOKIE)
    auth_session = auth_store.get(token)
    if auth_session is None:
        raise HTTPException(status_code=401, detail="Sign in with OpenCode Go to continue.")
    new_token = auth_store.rotate(token, auth_session.api_key, auth_session.model)
    if new_token is None:
        raise HTTPException(status_code=401, detail="Sign in with OpenCode Go to continue.")
    set_session_cookie(response, new_token)
    return {"authenticated": True, "model": auth_session.model or DEFAULT_MODEL}


@router.post("/settings/test")
async def test_connection(request: Request, payload: ConnectionTest) -> dict:
    """Send a tiny completion using the already signed-in Go credential."""
    auth_session = require_session(request)
    provider = get_provider("console", api_key=auth_session.api_key)
    model = DEFAULT_MODEL
    request_body = TurnRequest(
        session_id="connection-test",
        system="Reply with the single word: ready",
        messages=[{"role": "user", "content": "ready"}],
        model=model,
        max_tokens=16,
    )
    started = time.perf_counter()
    chunks: list[str] = []
    usage = None
    try:
        async for chunk in provider.stream(request_body):
            if chunk.delta:
                chunks.append(chunk)
            if chunk.usage:
                usage = chunk.usage
    except ProviderError as error:
        raise HTTPException(status_code=error.status or 502, detail=str(error)) from error

    return {
        "ok": True,
        "model": model,
        "reply": "".join(chunks).strip(),
        "latency_s": round(time.perf_counter() - started, 2),
        "cost_usd": usage.cost_usd if usage else None,
        "billing_source": usage.billing_source if usage else None,
    }


@router.get("/models")
async def models(request: Request) -> dict:
    auth_session = require_session(request)
    try:
        provider = get_provider("console", api_key=auth_session.api_key)
        catalogue = await provider.list_models()
        return {"provider": provider.name, "models": [model.__dict__ for model in catalogue]}
    except ProviderUnavailable as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=error.status or 502, detail=str(error)) from error
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="OpenCode did not respond in time.") from error


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(request: Request, payload: SessionCreate) -> SessionCreateResponse:
    auth_session = require_session(request)
    try:
        provider = get_provider("console", api_key=auth_session.api_key)
    except ProviderUnavailable as error:
        raise HTTPException(status_code=501, detail=str(error)) from error

    prompt = payload.prompt.strip()
    topics = list(payload.topics)
    if prompt and not topics:
        topics = [prompt[:200]]

    model = DEFAULT_MODEL

    try:
        session = store.create(
            language_id=payload.language,
            tone_id=payload.tone,
            mode=payload.mode,
            topics=topics,
            vocab_terms=list(payload.vocab_terms),
            level=DEFAULT_LEVEL,
            target_level=DEFAULT_LEVEL,
            provider=provider.name,
            model=model,
        )
    except ActiveSessionExists as error:
        active = store.active
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(error),
                "active_session_id": active.id if active else None,
            },
        ) from error

    auth_store.bind_learning_session(request.cookies.get(SESSION_COOKIE) or "", session.id)
    return _session_payload(session)


@router.get("/sessions/active")
async def read_active_session(request: Request) -> dict:
    """The session owned by the signed-in browser, if any."""
    require_session(request)
    state = auth_store.get_state(request.cookies.get(SESSION_COOKIE))
    session = store.active
    if session is None or state is None or state.learning_session_id != session.id:
        raise HTTPException(status_code=404, detail="No active session.")
    return {
        "session": _session_payload(session).model_dump(),
        "messages": [message.__dict__ for message in session.messages],
        "observations": [observation.__dict__ for observation in session.observations],
        "usage": session.usage,
    }


@router.delete("/sessions/active", response_model=DiscardResponse)
async def discard_active_session(request: Request) -> DiscardResponse:
    require_session(request)
    session = store.active
    if session is not None:
        auth_store.unbind_learning_session(
            request.cookies.get(SESSION_COOKIE) or "", session.id
        )
    return DiscardResponse(discarded=store.discard())


@router.get("/sessions/{session_id}")
async def read_session(request: Request, session_id: str) -> dict:
    require_owned_learning_session(request, session_id)
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or already discarded.")
    return {
        "session": _session_payload(session).model_dump(),
        "messages": [message.__dict__ for message in session.messages],
        "observations": [observation.__dict__ for observation in session.observations],
        "usage": session.usage,
    }


@router.post("/sessions/{session_id}/turns")
async def create_turn(request: Request, session_id: str, body: dict) -> StreamingResponse:
    auth_session = require_owned_learning_session(request, session_id)
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or already discarded.")

    text = str(body.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message.")

    try:
        provider = get_provider("console", api_key=auth_session.api_key)
    except ProviderUnavailable as error:
        raise HTTPException(status_code=501, detail=str(error)) from error

    language = resolve_language(session.language_id)
    tone = resolve_tone(session.tone_id)

    session.add_message("user", text, mode=session.mode)
    history = [
        {"role": message.role, "content": message.content}
        for message in session.messages
        if message.role in {"user", "assistant"}
    ]
    system = build_system_prompt(
        language=language,
        tone=tone,
        level=session.level,
        target_level=session.target_level,
        topics=session.topics,
        vocab_terms=session.vocab_terms,
    )

    async def event_stream() -> AsyncIterator[str]:
        raw_parts: list[str] = []
        succeeded = True

        async def run_turn(model: str) -> AsyncIterator[str]:
            """Stream one turn. Sets ``succeeded`` to False if it fails."""
            nonlocal succeeded
            request = TurnRequest(
                session_id=session.id,
                system=system,
                messages=history,
                model=model,
            )
            try:
                async for chunk in provider.stream(request):
                    if chunk.delta:
                        raw_parts.append(chunk.delta)
                        yield _sse("delta", {"text": chunk.delta})
                    if chunk.usage:
                        session.usage["input_tokens"] = (
                            session.usage.get("input_tokens", 0) + chunk.usage.input_tokens
                        )
                        session.usage["output_tokens"] = (
                            session.usage.get("output_tokens", 0) + chunk.usage.output_tokens
                        )
                        if chunk.usage.cost_usd is not None:
                            session.usage["cost_usd"] = round(
                                session.usage.get("cost_usd", 0.0) + chunk.usage.cost_usd, 6
                            )
                        if chunk.usage.allowance_usd is not None:
                            session.usage["allowance_usd"] = round(
                                session.usage.get("allowance_usd", 0.0)
                                + chunk.usage.allowance_usd,
                                6,
                            )
                        yield _sse("usage", chunk.usage.__dict__)
            except ProviderError as error:
                succeeded = False
                yield _sse("error", {"message": str(error), "status": error.status})
            except Exception as error:  # noqa: BLE001 - surfaced to the client
                succeeded = False
                yield _sse("error", {"message": str(error)})

        async for event in run_turn(session.model):
            yield event

        if not succeeded:
            return

        raw = "".join(raw_parts)
        visible, notes = parse_notes(raw)
        if not visible.strip():
            # A small model sometimes answers with the machine-readable block
            # only. Fall back to its own next-step suggestion, then to a
            # neutral continuation, so the learner never sees an empty bubble.
            visible = notes.next_step.strip() or continuation_fallback(session.language_id)
        session.add_message("assistant", visible)

        for note in notes.vocab:
            session.add_observation(
                Observation(
                    kind="vocab",
                    term=note.term,
                    status=note.status,
                    meaning=note.meaning,
                    evidence=note.evidence,
                )
            )
        for note in notes.grammar:
            session.add_observation(
                Observation(
                    kind="grammar",
                    term=note.concept,
                    status=note.status,
                    note=note.note,
                )
            )

        if notes.level_delta:
            delta = sum(notes.level_delta.values())
            session.level = clamp_delta(session.level, delta)
            session.target_level = session.level

        if notes.next_step:
            session.next_steps.append(notes.next_step)

        yield _sse(
            "notes",
            {
                "reply": visible,
                "vocab": [vars(note) for note in notes.vocab],
                "grammar": [vars(note) for note in notes.grammar],
                "level": session.level,
                "next_step": notes.next_step,
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/end")
async def end_session(request: Request, session_id: str) -> dict:
    require_owned_learning_session(request, session_id)
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or already discarded.")
    from datetime import UTC, datetime

    session.status = "ended"
    session.ended_at = datetime.now(UTC).isoformat(timespec="seconds")
    return {"status": session.status, "ended_at": session.ended_at, "level": session.level}


@router.delete("/sessions/{session_id}", response_model=DiscardResponse)
async def discard_session(request: Request, session_id: str) -> DiscardResponse:
    require_owned_learning_session(request, session_id)
    auth_store.unbind_learning_session(request.cookies.get(SESSION_COOKIE) or "", session_id)
    return DiscardResponse(discarded=store.discard(session_id))


@router.post("/sessions/{session_id}/recap.pdf")
async def recap_pdf(request: Request, session_id: str) -> Response:
    """Render the session recap as a PDF.

    The PDF is the only durable artefact of a session: transcripts and notes
    live in memory and disappear when Marasa closes.
    """
    require_owned_learning_session(request, session_id)
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or already discarded.")

    from .export.pdf import html_to_pdf, render_recap_html
    from .tutor.rubric import get_level

    level = get_level(session.level)
    html = render_recap_html(
        session,
        level={
            "code": level.code,
            "label": level.label,
            "summary": level.summary,
        },
        next_steps=session.next_steps,
    )
    pdf = await html_to_pdf(html)
    filename = f"marasa-recap-{session.id[:8]}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
