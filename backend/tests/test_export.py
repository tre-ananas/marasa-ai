"""Recap PDF rendering tests.

The Windows regression guard matters: uvicorn switches to a selector event
loop when --reload is enabled, and a selector loop cannot spawn subprocesses,
which is how Playwright starts its driver. The renderer must work under both
event-loop policies.
"""

import asyncio
import sys
from pathlib import Path

import pytest

from app.export.pdf import html_to_pdf, render_recap_html
from app.session import Observation, Session
from app.tutor.rubric import get_level

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
BROWSER_AVAILABLE = sys.platform != "win32" or EDGE.exists()

needs_browser = pytest.mark.skipif(
    not BROWSER_AVAILABLE, reason="no headless browser available (Edge not installed)"
)


def _sample_session() -> Session:
    session = Session(
        id="session1234abcd",
        language_id="es",
        tone_id="conversation_partner",
        mode="text",
        topics=["Hablemos de comida"],
        level="IM",
        provider="ollama",
        model="qwen3:8b",
    )
    session.add_message("user", "Me encanta la pasta fresca.")
    session.add_message("assistant", "¿Cuál es tu plato favorito?")
    session.add_observation(
        Observation(kind="vocab", term="pasta", status="strong", meaning="masa", evidence="pasta")
    )
    session.add_observation(
        Observation(kind="grammar", term="uso de 'me encanta'", status="strong", note="correcto")
    )
    session.next_steps.append("Practica el pasado la próxima vez.")
    return session


def test_recap_html_contains_the_observations() -> None:
    session = _sample_session()
    level = get_level(session.level)
    html = render_recap_html(
        session,
        level={"code": level.code, "label": level.label, "summary": level.summary},
        next_steps=session.next_steps,
    )
    assert "pasta" in html
    assert "me encanta" in html
    assert "Practica el pasado" in html
    assert "not an official ACTFL" in html


@needs_browser
def test_pdf_renders_under_a_selector_event_loop() -> None:
    """Windows + `uvicorn --reload` uses a selector loop; the PDF must still work."""
    previous = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        pdf = asyncio.run(html_to_pdf("<html><body><h1>Marasa</h1></body></html>"))
    finally:
        asyncio.set_event_loop_policy(previous)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000
