import json

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_provider() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "mock"


def test_settings_lists_three_languages_and_tones() -> None:
    client = TestClient(create_app())
    payload = client.get("/api/settings").json()
    language_ids = {language["id"] for language in payload["languages"]}
    assert {"es", "ar-lev", "sv"} <= language_ids
    assert payload["tones"]


def test_second_session_is_rejected_until_discarded() -> None:
    client = TestClient(create_app())
    first = client.post("/api/sessions", json={"prompt": "Tell me about your week"})
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    second = client.post("/api/sessions", json={"prompt": "Another topic"})
    assert second.status_code == 409
    # The conflict tells the client which session is in the way, so the UI can
    # offer to discard it even after a page reload lost the id.
    detail = second.json()["detail"]
    assert detail["active_session_id"] == session_id

    assert client.delete(f"/api/sessions/{session_id}").json() == {"discarded": True}
    third = client.post("/api/sessions", json={"prompt": "Another topic"})
    assert third.status_code == 200


def test_active_session_can_be_found_and_discarded_without_its_id() -> None:
    """After a page reload the UI loses the session id; it must still recover."""
    client = TestClient(create_app())
    assert client.get("/api/sessions/active").status_code == 404

    session_id = client.post("/api/sessions", json={"prompt": "Tell me about your week"}).json()[
        "session_id"
    ]

    active = client.get("/api/sessions/active")
    assert active.status_code == 200
    assert active.json()["session"]["session_id"] == session_id

    assert client.delete("/api/sessions/active").json() == {"discarded": True}
    assert client.get("/api/sessions/active").status_code == 404
    # And a new session can now start.
    assert client.post("/api/sessions", json={"prompt": "Fresh start"}).status_code == 200


def test_turn_streams_reply_and_notes() -> None:
    client = TestClient(create_app())
    session_id = client.post("/api/sessions", json={"prompt": "Vamos a hablar"}).json()[
        "session_id"
    ]

    with client.stream(
        "POST", f"/api/sessions/{session_id}/turns", json={"text": "Me gusta aprender"}
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: delta" in body
    assert "event: notes" in body
    assert "vocab" in body


def test_notes_only_answer_never_shows_an_empty_bubble(monkeypatch) -> None:
    """A small model may answer with the machine-readable block only."""

    class NotesOnlyProvider:
        name = "mock"
        default_model = "mock-chat"

        async def list_models(self) -> list:
            return []

        async def stream(self, request):
            from app.providers.base import StreamChunk

            yield StreamChunk(
                delta=(
                    '<marasa_notes>\n{"vocab": [], "grammar": [], '
                    '"level_delta": {"vocab": 0}, "next_step": "Practice past tense next."}'
                    "\n</marasa_notes>"
                )
            )

    monkeypatch.setattr("app.api.get_provider", lambda *args, **kwargs: NotesOnlyProvider())

    client = TestClient(create_app())
    session_id = client.post(
        "/api/sessions", json={"prompt": "Hablemos", "language": "es"}
    ).json()["session_id"]

    with client.stream(
        "POST", f"/api/sessions/{session_id}/turns", json={"text": "Me gusta aprender"}
    ) as response:
        body = "".join(response.iter_text())

    notes_line = [line for line in body.splitlines() if line.startswith("data: ")][-1]
    payload = json.loads(notes_line[6:])
    assert payload["reply"].strip(), "the learner must never see an empty message"
    assert "Practice past tense next." in payload["reply"]
