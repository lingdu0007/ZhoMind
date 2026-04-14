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
        payload = response.json()
        assert set(payload.keys()) == {"username", "role"}
        assert payload["username"] == username
        assert payload["role"] == "user"


def test_session_get_shape_and_delete_route() -> None:
    username = f"session_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)

        get_resp = client.get("/api/v1/sessions", headers=_auth_headers(token))
        assert get_resp.status_code == 200
        get_payload = get_resp.json()
        assert set(get_payload.keys()) == {"items"}
        assert isinstance(get_payload["items"], list)


def test_chat_and_chat_stream_routes_match_contract() -> None:
    with TestClient(app) as client:
        chat_resp = client.post("/api/v1/chat", json={"message": "hello"})
        assert chat_resp.status_code == 200
        chat_payload = chat_resp.json()
        assert set(chat_payload.keys()) == {"session_id", "message"}
        assert chat_payload["message"]["role"] == "assistant"

        with client.stream("POST", "/api/v1/chat/stream", json={"message": "hello"}) as stream_resp:
            assert stream_resp.status_code == 200
            assert stream_resp.headers.get("content-type", "").startswith("text/event-stream")
            body = "".join(stream_resp.iter_text())
            assert "event: meta" in body
            assert "event: content" in body
            assert "event: done" in body
