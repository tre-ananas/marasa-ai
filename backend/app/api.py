"""HTTP API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .config import get_settings
from .providers.base import TurnRequest
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


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    model = settings.model
    try:
        provider = get_provider()
        model = model or getattr(provider, "default_model", model)
    except ProviderUnavailable:
        pass
    return {
        "ok": True,
        "app": settings.app_name,
        "provider": settings.provider,
        "model": model,
        "key_configured": settings.key_configured,
        "active_session": store.active.id if store.active else None,
    }


@router.get("/settings")
async def read_settings() -> dict:
    settings = get_settings()
    return {
        "provider": settings.provider,
        "model": settings.model,
        "key_configured": settings.key_configured,
        "pdf_engine": settings.pdf_engine,
        "languages": [
            {"id": lang.id, "label": lang.label, "stt_locale": lang.stt_locale}
            for lang in LANGUAGES.values()
        ],
        "tones": [
            {"id": tone.id, "label": tone.label, "blurb": tone.blurb} for tone in TONES.values()
        ],
    }


@router.get("/models")
async def models() -> dict:
    settings = get_settings()
    try:
        provider = get_provider()
        return {"provider": provider.name, "models": [m.__dict__ for m in await provider.list_models()]}
    except ProviderUnavailable as error:
        raise HTTPException(status_code=501, detail=str(error)) from error


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(payload: SessionCreate) -> SessionCreateResponse:
    settings = get_settings()
    try:
        provider = get_provider()
    except ProviderUnavailable as error:
        raise HTTPException(status_code=501, detail=str(error)) from error

    prompt = payload.prompt.strip()
    topics = list(payload.topics)
    if prompt and not topics:
        topics = [prompt[:200]]

    model = settings.model or getattr(provider, "default_model", "") or settings.model

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

    return _session_payload(session)


@router.get("/sessions/active")
async def read_active_session() -> dict:
    """The session that is currently running, if any.

    The UI loses its session id when the page is reloaded, so it needs a way to
    find (and resume, or discard) the session the backend still holds.
    """
    session = store.active
    if session is None:
        raise HTTPException(status_code=404, detail="No active session.")
    return {
        "session": _session_payload(session).model_dump(),
        "messages": [message.__dict__ for message in session.messages],
        "observations": [observation.__dict__ for observation in session.observations],
        "usage": session.usage,
    }


@router.delete("/sessions/active", response_model=DiscardResponse)
async def discard_active_session() -> DiscardResponse:
    return DiscardResponse(discarded=store.discard())


@router.get("/sessions/{session_id}")
async def read_session(session_id: str) -> dict:
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
async def create_turn(session_id: str, body: dict) -> StreamingResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or already discarded.")

    text = str(body.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message.")

    try:
        provider = get_provider(session.provider)
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
        request = TurnRequest(
            session_id=session.id,
            system=system,
            messages=history,
            model=session.model,
        )

        raw_parts: list[str] = []
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
                    yield _sse("usage", chunk.usage.__dict__)
        except Exception as error:  # noqa: BLE001 - surfaced to the client as an event
            yield _sse("error", {"message": str(error)})
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
async def end_session(session_id: str) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or already discarded.")
    from datetime import UTC, datetime

    session.status = "ended"
    session.ended_at = datetime.now(UTC).isoformat(timespec="seconds")
    return {"status": session.status, "ended_at": session.ended_at, "level": session.level}


@router.delete("/sessions/{session_id}", response_model=DiscardResponse)
async def discard_session(session_id: str) -> DiscardResponse:
    return DiscardResponse(discarded=store.discard(session_id))


@router.post("/sessions/{session_id}/recap.pdf")
async def recap_pdf(session_id: str) -> Response:
    """Render the session recap as a PDF.

    The PDF is the only durable artefact of a session: transcripts and notes
    live in memory and disappear when Marasa closes.
    """
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
