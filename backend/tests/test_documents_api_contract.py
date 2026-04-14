from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_user(client: TestClient, *, username: str, role: str = "user") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": role},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["username"] == username
    assert payload["role"] == role
    return payload["access_token"]


def test_auth_register_returns_tokens() -> None:
    username = f"new_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        assert token


def test_auth_me_returns_current_user() -> None:
    username = f"me_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        response = client.get("/api/v1/auth/me", headers=_auth_headers(token))
        assert response.status_code == 200
        assert response.json() == {"username": username, "role": "user"}


def test_get_session_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/ses_123")
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_INVALID_TOKEN"


def test_delete_session_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.delete("/api/v1/sessions/ses_123")
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_INVALID_TOKEN"


def test_chat_post_returns_chat_response_shape() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "hi"})
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"session_id", "message"}
        assert body["message"]["role"] == "assistant"
        assert "message_id" in body["message"]
        assert "timestamp" in body["message"]


def test_chat_stream_post_returns_sse() -> None:
    with TestClient(app) as client:
        with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi"}) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            payload = "".join(response.iter_text())
            assert "event: meta" in payload
            assert "event: content" in payload
            assert "event: done" in payload
