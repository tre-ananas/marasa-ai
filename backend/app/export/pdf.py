"""Recap PDF rendering.

The recap is rendered as HTML (one print stylesheet, one template) and printed
to PDF by a headless browser. Rendering the same markup that the UI uses keeps
the PDF visually consistent with the app and handles every target script
(Arabic, Chinese, Swedish) without shipping font files.

Browser choice:
- ``edge``     uses the Microsoft Edge already installed on Windows — no download
- ``chromium`` uses Playwright's bundled Chromium (``playwright install chromium``)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import get_settings
from ..session import Session

TEMPLATE_DIR = Path(__file__).parent / "templates"

_environment = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_recap_html(
    session: Session,
    *,
    level: dict,
    next_steps: list[str],
) -> str:
    vocab = [observation for observation in session.observations if observation.kind == "vocab"]
    grammar = [observation for observation in session.observations if observation.kind == "grammar"]
    template = _environment.get_template("recap.html.j2")
    return template.render(
        session=session,
        level=level,
        topics=session.topics,
        vocab=vocab,
        grammar=grammar,
        next_steps=next_steps,
        messages=session.messages,
    )


async def html_to_pdf(html: str) -> bytes:
    """Render HTML to PDF bytes with a headless browser.

    The rendering runs in a worker thread using Playwright's *sync* API.
    Playwright's async API starts its driver through
    ``asyncio.create_subprocess_exec``, which raises ``NotImplementedError``
    on a selector event loop — and uvicorn on Windows uses one whenever
    ``--reload`` is on. The sync API spawns the driver with a plain
    subprocess, so it works under every event loop.
    """
    return await asyncio.to_thread(_render_pdf_sync, html, get_settings().pdf_engine)


def _render_pdf_sync(html: str, engine: str) -> bytes:
    from playwright.sync_api import sync_playwright

    launch_options: dict = {"headless": True}
    if engine == "edge":
        launch_options["channel"] = "msedge"

    # Playwright's sync API creates its own event loop. On Windows the
    # process policy may be the selector policy (uvicorn switches to it when
    # --reload is enabled), and a selector loop cannot spawn subprocesses —
    # which is exactly how Playwright starts its driver. Temporarily install
    # the proactor policy while rendering, then restore the previous one.
    previous_policy = None
    if sys.platform == "win32":
        previous_policy = asyncio.get_event_loop_policy()
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_options)
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="load")
                return page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
                )
            finally:
                browser.close()
    finally:
        if previous_policy is not None:
            asyncio.set_event_loop_policy(previous_policy)
