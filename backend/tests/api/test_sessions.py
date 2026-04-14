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


def _seed_session(
    *,
    username: str,
    title: str,
    messages: list[dict[str, object]],
) -> tuple[str, int]:
    async def _run() -> tuple[str, int]:
        async with app.state.db.session_factory() as session:
            user = await UserRepository(session).get_by_username(username=username)
            assert user is not None

            session_repo = ChatSessionRepository(session)
            message_repo = ChatMessageRepository(session)
            chat_session = await session_repo.create_session(user_id=user.id, title=title)
            for message in messages:
                await message_repo.add_message(
                    session_id=chat_session.id,
                    role=str(message["role"]),
                    content=str(message["content"]),
                    rag_trace_json=message.get("rag_trace"),
                )
            await session.commit()
            return chat_session.id, len(messages)

    return asyncio.run(_run())


def test_session_list_detail_delete() -> None:
    username = f"session_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        session_id, message_count = _seed_session(
            username=username,
            title="Task 4 seeded session",
            messages=[
                {"role": "user", "content": "How does Task 4 work?"},
                {
                    "role": "assistant",
                    "content": "It persists sessions and messages.",
                    "rag_trace": {"sources": ["design-spec"]},
                },
            ],
        )
        headers = {"Authorization": f"Bearer {token}"}

        list_response = client.get("/api/v1/sessions", headers=headers)
        assert list_response.status_code == 200
        list_payload = list_response.json()
        assert isinstance(list_payload["items"], list)
        listed = next(item for item in list_payload["items"] if item["session_id"] == session_id)
        assert listed["title"] == "Task 4 seeded session"
        assert listed["message_count"] == message_count
        assert "updated_at" in listed

        detail_response = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["session_id"] == session_id
        assert len(detail_payload["messages"]) == 2
        assert detail_payload["messages"][0]["type"] == "user"
        assert detail_payload["messages"][0]["content"] == "How does Task 4 work?"
        assert "timestamp" in detail_payload["messages"][0]
        assert detail_payload["messages"][1]["type"] == "assistant"
        assert detail_payload["messages"][1]["rag_trace"] == {"sources": ["design-spec"]}

        delete_response = client.delete(f"/api/v1/sessions/{session_id}", headers=headers)
        assert delete_response.status_code == 204

        missing_response = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
        assert missing_response.status_code == 404
        assert missing_response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_session_detail_returns_message_shape() -> None:
    username = f"shape_user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        token = _register_user(client, username=username)
        session_id, _ = _seed_session(
            username=username,
            title="Shape session",
            messages=[
                {
                    "role": "assistant",
                    "content": "Structured session detail.",
                    "rag_trace": {"score": 0.92, "hits": 3},
                }
            ],
        )

        response = client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload["messages"], list)
        assert payload["messages"][0]["type"] in {"user", "assistant"}
        assert payload["messages"][0]["content"] == "Structured session detail."
        assert "timestamp" in payload["messages"][0]
        assert payload["messages"][0]["rag_trace"] == {"score": 0.92, "hits": 3}


def test_session_detail_is_user_isolated() -> None:
    owner_username = f"owner_{uuid4().hex[:8]}"
    other_username = f"other_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        _register_user(client, username=owner_username)
        other_token = _register_user(client, username=other_username)
        session_id, _ = _seed_session(
            username=owner_username,
            title="Owner only session",
            messages=[{"role": "user", "content": "Private message"}],
        )

        response = client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"
