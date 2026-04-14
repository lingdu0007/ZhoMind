from datetime import datetime

from pydantic import BaseModel


class SessionItem(BaseModel):
    session_id: str
    title: str | None = None
    message_count: int = 0
    updated_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionItem]


class SessionMessageItem(BaseModel):
    type: str
    content: str
    timestamp: datetime
    rag_trace: dict | None = None


class SessionDetailResponse(BaseModel):
    session_id: str
    messages: list[SessionMessageItem]
