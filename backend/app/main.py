"""Marasa AI — FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .api import router
from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    # The Vite dev server runs on a different port; in production the built
    # frontend is served by this app, so CORS is only needed for development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    dist = settings.frontend_dist
    assets_dir = dist / "assets"
    if assets_dir.is_dir():

        @app.get("/assets/{path:path}", include_in_schema=False)
        async def bundled_asset(path: str) -> FileResponse:
            candidate = (assets_dir / path).resolve()
            if not candidate.is_file() or assets_dir.resolve() not in candidate.parents:
                raise HTTPException(status_code=404, detail="Not found")
            # File names are content-hashed, so they can be cached forever.
            return FileResponse(
                candidate,
                headers={"Cache-Control": "public, max-age=31536000, immutable"},
            )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> FileResponse:
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            # The shell must always be revalidated, or a phone keeps running
            # an old bundle after an update (the asset file names are hashed).
            return FileResponse(
                dist / "index.html",
                headers={"Cache-Control": "no-cache, must-revalidate"},
            )

    return app


app = create_app()

