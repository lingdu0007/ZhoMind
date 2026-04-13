from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _auth_headers(token: str = "admin-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_register_returns_201_and_tokens() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "new_user", "password": "new-user-password", "role": "user"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "Bearer"
    assert payload["username"] == "new_user"
    assert payload["role"] == "user"


def test_auth_me_returns_current_user() -> None:
    response = client.get("/api/v1/auth/me", headers=_auth_headers("admin-token"))
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"username", "role"}
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"


def test_session_get_shape_and_delete_route() -> None:
    sid = "ses_contract_ok"
    get_resp = client.get(f"/api/v1/sessions/{sid}")
    assert get_resp.status_code == 200
    get_payload = get_resp.json()
    assert set(get_payload.keys()) == {"session_id", "items"}
    assert get_payload["session_id"] == sid
    assert isinstance(get_payload["items"], list)

    delete_resp = client.delete(f"/api/v1/sessions/{sid}")
    assert delete_resp.status_code == 204


def test_chat_and_chat_stream_routes_match_contract() -> None:
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
