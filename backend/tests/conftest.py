"""Test configuration.

The suite must be deterministic and offline regardless of the developer's local
``.env`` (which may point at a real provider). We pin the mock provider before
the application settings are first read.
"""

import os

import pytest

os.environ["MARASA_PROVIDER"] = "console"
os.environ["MARASA_MODEL"] = "mock-chat"
os.environ["MARASA_OPENCODE_API_KEY"] = ""

from app.auth import auth_store  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.session import store  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_session_store():
    """Sessions are in-memory and single-use; never leak one into another test."""
    store.clear()
    auth_store._sessions.clear()
    yield
    store.clear()
    auth_store._sessions.clear()
