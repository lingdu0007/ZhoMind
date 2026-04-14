import asyncio
import json
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


def _read_session_messages(session_id: str) -> list[dict[str, object]]:
    async def _run() -> list[dict[str, object]]:
        async with app.state.db.session_factory() as session:
            messages = await ChatMessageRepository(session).list_messages_for_session(session_id=session_id)
            return [
                {
                    "role": item.role,
                    "content": item.content,
                    "rag_trace": item.rag_trace_json,
                }
                for item in messages
            ]

    return asyncio.run(_run())


def _collect_sse(response) -> tuple[list[tuple[str, dict]], str]:
    body = "".join(response.iter_text())
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    for raw_line in body.splitlines():
        if raw_line.startswith("event: "):
            current_event = raw_line[len("event: ") :]
        elif raw_line.startswith("data: ") and current_event is not None:
            events.append((current_event, json.loads(raw_line[len("data: ") :])))
            current_event = None
    return events, body


def test_chat_stream_persists_messages_for_authenticated_user() -> None:
    username = f"stream_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Explain streaming retrieval persistence"},
            headers=_auth_headers(token),
        ) as response:
            assert response.status_code == 200
            events, _ = _collect_sse(response)

        meta = next(data for name, data in events if name == "meta")
        trace = next(data for name, data in events if name == "trace")
        assert meta["session_id"].startswith("session_")
        assert trace["retrieval"]["user_id"] == username
        assert _count_session_messages(meta["session_id"]) == 2

        detail = client.get(f"/api/v1/sessions/{meta['session_id']}", headers=_auth_headers(token))
        assert detail.status_code == 200
        messages = detail.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["type"] == "user"
        assert messages[1]["type"] == "assistant"
        assert messages[1]["rag_trace"] is not None


def test_chat_stream_reuses_existing_session_for_authenticated_user() -> None:
    username = f"stream_reuse_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        session_id = _seed_session(username=username, title="Existing stream chat")

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Continue streamed session", "session_id": session_id},
            headers=_auth_headers(token),
        ) as response:
            assert response.status_code == 200
            events, _ = _collect_sse(response)

        meta = next(data for name, data in events if name == "meta")
        assert meta["session_id"] == session_id
        assert _count_session_messages(session_id) == 2


def test_chat_stream_rejects_foreign_session_for_authenticated_user() -> None:
    owner_username = f"stream_owner_{uuid4().hex[:8]}"
    other_username = f"stream_other_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        owner_token = _register_user(client, username=owner_username)
        other_token = _register_user(client, username=other_username)

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Owner stream seed"},
            headers=_auth_headers(owner_token),
        ) as response:
            assert response.status_code == 200
            owner_events, _ = _collect_sse(response)

        owner_session_id = next(data for name, data in owner_events if name == "meta")["session_id"]

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Hijack stream", "session_id": owner_session_id},
            headers=_auth_headers(other_token),
        ) as response:
            assert response.status_code == 200
            _, body = _collect_sse(response)

        assert "event: error" in body
        assert '"code": "RESOURCE_NOT_FOUND"' in body
        assert _count_session_messages(owner_session_id) == 2


def test_chat_stream_anonymous_keeps_response_contract_without_persistence() -> None:
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Anonymous stream question"},
        ) as response:
            assert response.status_code == 200
            events, body = _collect_sse(response)

        meta = next(data for name, data in events if name == "meta")
        trace = next(data for name, data in events if name == "trace")
        assert meta["session_id"].startswith("ses_")
        assert trace["retrieval"]["user_id"] == meta["session_id"]
        assert "event: done" in body


def test_chat_stream_persists_rejected_answer_with_trace_for_authenticated_user() -> None:
    username = f"stream_reject_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "quantum grape nebula banana"},
            headers=_auth_headers(token),
        ) as response:
            assert response.status_code == 200
            events, _ = _collect_sse(response)

        meta = next(data for name, data in events if name == "meta")
        stored_messages = _read_session_messages(meta["session_id"])
        assert len(stored_messages) == 2
        assert stored_messages[1]["role"] == "assistant"
        assert "未检索到足够相关的知识片段" in str(stored_messages[1]["content"])
        stored_trace = stored_messages[1]["rag_trace"]
        assert isinstance(stored_trace, dict)
        assert stored_trace["metrics"]["gate_passed"] is False
