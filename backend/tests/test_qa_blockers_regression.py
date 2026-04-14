from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_user(client: TestClient, *, username: str, role: str = "user") -> str:
    payload = {"username": username, "password": "secret123", "role": role}
    if role == "admin":
        payload["admin_code"] = "letmein"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    assert response.json()["username"] == username
    return response.json()["access_token"]


def test_auth_register_meet_contract() -> None:
    username = f"qa_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        assert token


def test_auth_me_returns_200_with_current_user() -> None:
    username = f"qa_me_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        response = client.get("/api/v1/auth/me", headers=_auth(token))
        assert response.status_code == 200
        payload = response.json()
        assert set(payload.keys()) == {"username", "role"}
        assert payload["username"] == username
        assert payload["role"] == "user"


def test_sessions_detail_and_delete_contract() -> None:
    username = f"qa_session_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)

        detail = client.get("/api/v1/sessions/missing_session", headers=_auth(token))
        assert detail.status_code == 404
        detail_payload = detail.json()
        assert detail_payload["code"] == "RESOURCE_NOT_FOUND"

        delete = client.delete("/api/v1/sessions/missing_session", headers=_auth(token))
        assert delete.status_code == 404
        assert delete.json()["code"] == "RESOURCE_NOT_FOUND"


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
