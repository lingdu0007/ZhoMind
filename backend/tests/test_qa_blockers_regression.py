from fastapi.testclient import TestClient

from src.main import app


def _auth(token: str = "admin-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_register_meet_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "qa_user_01", "password": "password123", "role": "user"},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["token_type"] == "Bearer"
        assert payload["username"] == "qa_user_01"
        assert payload["role"] == "user"


def test_auth_me_returns_200_with_current_user() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers=_auth("admin-token"))
        assert response.status_code == 200
        payload = response.json()
        assert set(payload.keys()) == {"username", "role"}
        assert payload["role"] == "admin"


def test_sessions_detail_and_delete_contract() -> None:
    with TestClient(app) as client:
        detail = client.get("/api/v1/sessions/ses_01")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert set(detail_payload.keys()) == {"session_id", "items"}

        delete = client.delete("/api/v1/sessions/ses_01")
        assert delete.status_code == 204


def test_chat_and_chat_stream_contract() -> None:
    with TestClient(app) as client:
        chat = client.post("/api/v1/chat", json={"message": "hello"})
        assert chat.status_code == 200
        chat_payload = chat.json()
        assert set(chat_payload.keys()) == {"session_id", "message"}

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "hello stream"},
        ) as stream_resp:
            assert stream_resp.status_code == 200
            body = "".join(x for x in stream_resp.iter_text())
            assert "event: meta" in body
            assert "event: content" in body
            assert "event: done" in body
