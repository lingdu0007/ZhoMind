from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_auth_register_returns_201_and_tokens() -> None:
    payload = {
        "username": "new_user_1",
        "password": "password123",
        "role": "user",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {
        "access_token",
        "token_type",
        "expires_in",
        "refresh_token",
        "username",
        "role",
    }
    assert body["token_type"] == "Bearer"
    assert body["username"] == payload["username"]
    assert body["role"] == payload["role"]


def test_auth_me_returns_current_user() -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer user-token"})
    assert response.status_code == 200
    assert response.json() == {"username": "user-token", "role": "user"}


def test_get_session_returns_session_id_and_items_shape() -> None:
    response = client.get("/api/v1/sessions/ses_123")
    assert response.status_code == 200
    assert response.json() == {"session_id": "ses_123", "items": []}


def test_delete_session_exists_and_returns_204() -> None:
    response = client.delete("/api/v1/sessions/ses_123")
    assert response.status_code == 204
    assert response.content == b""


def test_chat_post_returns_chat_response_shape() -> None:
    response = client.post("/api/v1/chat", json={"message": "hi"})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"session_id", "message"}
    assert body["message"]["role"] == "assistant"
    assert "message_id" in body["message"]
    assert "timestamp" in body["message"]


def test_chat_stream_post_returns_sse() -> None:
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        chunks = list(response.iter_text())
        payload = "".join(chunks)
        assert "event: meta" in payload
        assert "event: content" in payload
        assert "event: done" in payload
