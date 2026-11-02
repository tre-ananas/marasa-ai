"""Runtime configuration.

Settings come from the environment (``.env`` at the repo root is loaded automatically).
Secrets are read here and never leave the backend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Marasa AI"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = REPO_ROOT / "data"

    # provider: mock | console | local | ollama
    provider: str = "mock"
    # Empty means "use the provider's default model".
    model: str = ""

    opencode_api_key: str | None = None
    opencode_base_url: str = "https://opencode.ai/inference"
    opencode_go_base_url: str = "https://opencode.ai/inference/go"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_num_ctx: int = 8192

    # chromium | edge
    pdf_engine: str = "edge"

    @property
    def frontend_dist(self) -> Path:
        return REPO_ROOT / "frontend" / "dist"

    @property
    def key_configured(self) -> bool:
        return bool(self.opencode_api_key)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    data_dir = Path(_env("MARASA_DATA_DIR", str(REPO_ROOT / "data"))).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        host=_env("MARASA_HOST", "127.0.0.1") or "127.0.0.1",
        port=int(_env("MARASA_PORT", "8000") or "8000"),
        data_dir=data_dir,
        provider=(_env("MARASA_PROVIDER", "mock") or "mock").lower(),
        model=_env("MARASA_MODEL", "") or "",
        opencode_api_key=_env("MARASA_OPENCODE_API_KEY"),
        opencode_base_url=_env(
            "MARASA_OPENCODE_BASE_URL", "https://opencode.ai/inference"
        )
        or "https://opencode.ai/inference",
        opencode_go_base_url=_env(
            "MARASA_OPENCODE_GO_BASE_URL", "https://opencode.ai/inference/go"
        )
        or "https://opencode.ai/inference/go",
        ollama_base_url=_env("OLLAMA_HOST", "http://127.0.0.1:11434")
        or "http://127.0.0.1:11434",
        ollama_model=_env("MARASA_OLLAMA_MODEL", "qwen3:8b") or "qwen3:8b",
        ollama_num_ctx=int(_env("MARASA_OLLAMA_NUM_CTX", "8192") or "8192"),
        pdf_engine=(_env("MARASA_PDF_ENGINE", "edge") or "edge").lower(),
    )
