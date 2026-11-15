import json

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_opencode_go() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "console"
    assert payload["endpoint"] == "go"


def test_settings_lists_three_languages_and_tones() -> None:
    client = TestClient(create_app())
    payload = client.get("/api/settings").json()
    language_ids = {language["id"] for language in payload["languages"]}
    assert {"es", "ar-lev", "sv"} <= language_ids
    assert payload["tones"]
    assert payload["authenticated"] is False


def test_sessions_require_opencode_sign_in() -> None:
    client = TestClient(create_app())
    response = client.post("/api/sessions", json={"prompt": "Tell me about your week"})
    assert response.status_code == 401


def test_sign_in_keeps_key_out_of_responses_and_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.providers.opencode_console.OpenCodeConsoleProvider.list_models",
        _async_return_models(),
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/auth/opencode/sign-in",
        json={"api_key": "sk-private-test-key"},
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert "sk-private-test-key" not in response.text
    assert "HttpOnly" in response.headers["set-cookie"]

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["authenticated"] is True
    assert settings.json()["model"] == "minimax-m3"
    assert "sk-private-test-key" not in settings.text


def test_signed_in_session_can_create_and_use_a_learning_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.providers.opencode_console.OpenCodeConsoleProvider.list_models",
        _async_return_models(),
    )
    monkeypatch.setattr(
        "app.providers.opencode_console.OpenCodeConsoleProvider.stream",
        _async_stream_reply(),
    )
    client = TestClient(create_app())
    client.post(
        "/api/auth/opencode/sign-in",
        json={"api_key": "sk-private-test-key"},
    )
    first = client.post("/api/sessions", json={"prompt": "Tell me about your week"})
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    active = client.get("/api/sessions/active")
    assert active.status_code == 200
    assert active.json()["session"]["session_id"] == session_id

    with client.stream(
        "POST", f"/api/sessions/{session_id}/turns", json={"text": "Me gusta aprender"}
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: delta" in body
    assert "event: notes" in body
    assert "vocab" in body


def test_signed_out_client_cannot_read_another_users_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.providers.opencode_console.OpenCodeConsoleProvider.list_models",
        _async_return_models(),
    )
    client = TestClient(create_app())
    client.post(
        "/api/auth/opencode/sign-in",
        json={"api_key": "sk-private-test-key"},
    )
    session_id = client.post("/api/sessions", json={"prompt": "Private topic"}).json()[
        "session_id"
    ]

    other = TestClient(create_app())
    assert other.get(f"/api/sessions/{session_id}").status_code == 401
    assert other.get("/api/sessions/active").status_code == 401


def test_sign_out_discards_the_ephemeral_credential() -> None:
    client = TestClient(create_app())
    client.cookies.set("marasa_session", "not-a-real-session")
    assert client.get("/api/settings").json()["authenticated"] is False


def test_notes_only_answer_never_shows_an_empty_bubble(monkeypatch) -> None:
    """A small model may answer with the machine-readable block only."""

    class NotesOnlyProvider:
        name = "console"
        default_model = "mock-chat"

        async def list_models(self) -> list:
            return []

        def stream(self, request):
            from app.providers.base import StreamChunk

            yield StreamChunk(
                delta=(
                    '<marasa_notes>\n{"vocab": [], "grammar": [], '
                    '"level_delta": {"vocab": 0}, "next_step": "Practice past tense next."}'
                    "\n</marasa_notes>"
                )
            )

    monkeypatch.setattr(
        "app.providers.opencode_console.OpenCodeConsoleProvider.list_models",
        _async_return_models(),
    )
    monkeypatch.setattr(
        "app.providers.opencode_console.OpenCodeConsoleProvider.stream",
        _async_stream_notes_only(),
    )

    client = TestClient(create_app())
    sign_in = client.post(
        "/api/auth/opencode/sign-in",
        json={"api_key": "sk-private-test-key"},
    )
    assert sign_in.status_code == 200
    created = client.post(
        "/api/sessions", json={"prompt": "Hablemos", "language": "es"}
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]

    with client.stream(
        "POST", f"/api/sessions/{session_id}/turns", json={"text": "Me gusta aprender"}
    ) as response:
        body = "".join(response.iter_text())

    notes_line = [line for line in body.splitlines() if line.startswith("data: ")][-1]
    payload = json.loads(notes_line[6:])
    assert payload["reply"].strip(), "the learner must never see an empty message"
    assert "Practice past tense next." in payload["reply"]


def _async_stream_notes_only():
    from app.providers.base import StreamChunk

    async def stream(self, request):
        yield StreamChunk(
            delta=(
                '<marasa_notes>\n{"vocab": [], "grammar": [], '
                '"level_delta": {"vocab": 0}, "next_step": "Practice past tense next."}'
                "\n</marasa_notes>"
            )
        )

    return stream


def _async_stream_reply():
    from app.providers.base import StreamChunk

    async def stream(self, request):
        yield StreamChunk(delta="Great! <marasa_notes>{}</marasa_notes>")

    return stream


def _async_return_models():
    from app.providers.base import ModelInfo

    async def list_models(self):
        return [
            ModelInfo(
                id="minimax-m3",
                label="MiniMax M3",
                free=False,
                endpoint="messages",
            )
        ]

    return list_models
