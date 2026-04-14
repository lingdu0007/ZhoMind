from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.sessions.service import SessionService


@dataclass
class ChatService:
    session: AsyncSession
    rag_service: object

    def __post_init__(self) -> None:
        self._sessions = SessionService(self.session)

    async def chat(
        self,
        *,
        message: str,
        request_id: str,
        session_id: str | None = None,
        username: str | None = None,
    ) -> dict:
        if not username:
            resolved_session_id = session_id or f"ses_{uuid4().hex[:12]}"
            result = await self.rag_service.answer(message=message, session_id=resolved_session_id, request_id=request_id)
            if isinstance(result, dict):
                return result
            return {
                "session_id": result.session_id,
                "message": {
                    "message_id": result.message_id,
                    "role": "assistant",
                    "content": result.content,
                    "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "rag_trace": result.rag_trace,
                },
            }

        chat_session = await self._sessions.ensure_chat_session(username=username, session_id=session_id, opening_message=message)
        await self._sessions.add_chat_message(
            session_id=chat_session.id,
            role="user",
            content=message,
        )
        result = await self.rag_service.answer(
            message=message,
            session_id=chat_session.id,
            request_id=request_id,
            user_id=username,
        )
        persisted = await self._sessions.add_chat_message(
            session_id=chat_session.id,
            role="assistant",
            content=result.content,
            rag_trace=result.rag_trace,
        )
        await self.session.commit()
        return {
            "session_id": chat_session.id,
            "message": {
                "message_id": persisted.id,
                "role": "assistant",
                "content": persisted.content,
                "timestamp": persisted.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "rag_trace": persisted.rag_trace_json,
            },
        }
