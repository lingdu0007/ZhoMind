from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import ChatMessageModel, ChatSessionModel
from src.infrastructure.db.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
    UserRepository,
)
from src.shared.exceptions import AppError
from src.shared.schemas.sessions import (
    SessionDetailResponse,
    SessionItem,
    SessionListResponse,
    SessionMessageItem,
)


@dataclass
class SessionService:
    session: AsyncSession

    def __post_init__(self) -> None:
        self._users = UserRepository(self.session)
        self._sessions = ChatSessionRepository(self.session)
        self._messages = ChatMessageRepository(self.session)

    async def list_sessions(self, *, username: str) -> SessionListResponse:
        user = await self._require_user(username=username)
        sessions, _ = await self._sessions.list_sessions(user_id=user.id)
        return SessionListResponse(
            items=[
                SessionItem(
                    session_id=item.id,
                    title=item.title,
                    message_count=item.message_count,
                    updated_at=item.updated_at,
                )
                for item in sessions
            ]
        )

    async def get_session_detail(self, *, username: str, session_id: str) -> SessionDetailResponse:
        user = await self._require_user(username=username)
        chat_session = await self._sessions.get_session_for_user(user_id=user.id, session_id=session_id)
        if chat_session is None:
            raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)

        messages = await self._messages.list_messages_for_session(session_id=session_id)
        return SessionDetailResponse(
            session_id=chat_session.id,
            messages=[
                SessionMessageItem(
                    type="user" if item.role == "user" else "assistant",
                    content=item.content,
                    timestamp=item.created_at,
                    rag_trace=item.rag_trace_json,
                )
                for item in messages
            ],
        )

    async def delete_session(self, *, username: str, session_id: str) -> None:
        user = await self._require_user(username=username)
        deleted = await self._sessions.delete_session_for_user(user_id=user.id, session_id=session_id)
        if not deleted:
            raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
        await self.session.commit()

    async def ensure_chat_session(
        self,
        *,
        username: str,
        session_id: str | None,
        opening_message: str,
        create_if_missing: bool = False,
    ) -> ChatSessionModel:
        user = await self._require_user(username=username)
        if session_id:
            chat_session = await self._sessions.get_session_for_user(user_id=user.id, session_id=session_id)
            if chat_session is not None:
                return chat_session
            if not create_if_missing:
                raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
            existing_session = await self._sessions.get_session(session_id=session_id)
            if existing_session is not None:
                raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
            return await self._sessions.create_session(
                user_id=user.id,
                title=opening_message[:80].strip() or None,
                session_id=session_id,
            )
        return await self._sessions.create_session(user_id=user.id, title=opening_message[:80].strip() or None)

    async def add_chat_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        rag_trace: dict | None = None,
    ) -> ChatMessageModel:
        return await self._messages.add_message(
            session_id=session_id,
            role=role,
            content=content,
            rag_trace_json=rag_trace,
        )

    async def _require_user(self, *, username: str):
        user = await self._users.get_by_username(username=username)
        if user is None:
            raise AppError("AUTH_INVALID_TOKEN", "Invalid or expired token", status_code=401)
        return user
