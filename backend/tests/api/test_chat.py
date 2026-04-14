import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from src.infrastructure.db.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
    UserRepository,
)
from src.main import app


def _register_user(client: TestClient, *, username: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "user"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _count_session_messages(session_id: str) -> int:
    async def _run() -> int:
        async with app.state.db.session_factory() as session:
            messages = await ChatMessageRepository(session).list_messages_for_session(session_id=session_id)
            return len(messages)

    return asyncio.run(_run())


def _seed_session(*, username: str, title: str) -> str:
    async def _run() -> str:
        async with app.state.db.session_factory() as session:
            user = await UserRepository(session).get_by_username(username=username)
            assert user is not None
            chat_session = await ChatSessionRepository(session).create_session(user_id=user.id, title=title)
            await session.commit()
            return chat_session.id

    return asyncio.run(_run())


def test_chat_persists_messages_for_authenticated_user() -> None:
    username = f"chat_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)

        response = client.post(
            "/api/v1/chat",
            json={"message": "Explain retrieval orchestration"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["message"]["role"] == "assistant"
        assert payload["message"]["rag_trace"]["retrieval"]["user_id"] == username
        assert _count_session_messages(payload["session_id"]) == 2

        detail = client.get(f"/api/v1/sessions/{payload['session_id']}", headers=_auth_headers(token))
        assert detail.status_code == 200
        messages = detail.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["type"] == "user"
        assert messages[0]["content"] == "Explain retrieval orchestration"
        assert messages[1]["type"] == "assistant"
        assert messages[1]["rag_trace"] is not None


def test_chat_reuses_existing_session_for_authenticated_user() -> None:
    username = f"chat_reuse_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        session_id = _seed_session(username=username, title="Existing chat")

        response = client.post(
            "/api/v1/chat",
            json={"message": "Continue existing session", "session_id": session_id},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"] == session_id
        assert _count_session_messages(session_id) == 2


def test_chat_rejects_foreign_session_for_authenticated_user() -> None:
    owner_username = f"owner_{uuid4().hex[:8]}"
    other_username = f"other_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        _register_user(client, username=owner_username)
        other_token = _register_user(client, username=other_username)
        owner_session_id = _seed_session(username=owner_username, title="Owner session")

        response = client.post(
            "/api/v1/chat",
            json={"message": "Hijack session", "session_id": owner_session_id},
            headers=_auth_headers(other_token),
        )
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_chat_anonymous_keeps_response_contract_without_persistence() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "Anonymous question"})
        assert response.status_code == 200
        payload = response.json()
        assert "session_id" in payload
        assert payload["message"]["role"] == "assistant"
        assert payload["message"]["rag_trace"]["retrieval"]["user_id"] == payload["session_id"]


def test_chat_list_sessions_includes_new_chat_for_authenticated_user() -> None:
    username = f"chat_list_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)

        response = client.post(
            "/api/v1/chat",
            json={"message": "Create session from chat"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        listing = client.get("/api/v1/sessions", headers=_auth_headers(token))
        assert listing.status_code == 200
        items = listing.json()["items"]
        created = next(item for item in items if item["session_id"] == session_id)
        assert created["message_count"] == 2
        assert created["title"] == "Create session from chat"
