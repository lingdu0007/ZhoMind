import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_optional_subject
from src.application.chat.service import ChatService
from src.application.sessions.service import SessionService
from src.infrastructure.logging.observability import log_event, summarize_user_text
from src.shared.exceptions import AppError
from src.shared.request_context import request_id_ctx

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = None


@router.post("")
async def chat(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    subject: dict[str, str] | None = Depends(get_optional_subject),
) -> dict:
    session_id = payload.session_id or f"ses_{uuid4().hex[:12]}"
    request_id = getattr(request.state, "request_id", "") or request_id_ctx.get() or "unknown"

    log_event(
        logger,
        "INFO",
        "chat.request.started",
        request_id=request_id,
        session_id=session_id,
        input_summary=summarize_user_text(payload.message),
    )

    chat_service = ChatService(session=session, rag_service=request.app.state.rag_service)
    response = await asyncio.wait_for(
        chat_service.chat(
            message=payload.message,
            session_id=payload.session_id,
            request_id=request_id,
            username=subject["username"] if subject else None,
        ),
        timeout=10.0,
    )

    completed_message_id = response["message"]["message_id"]
    log_event(
        logger,
        "INFO",
        "chat.request.completed",
        request_id=request_id,
        session_id=response["session_id"],
        message_id=completed_message_id,
    )
    return response


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    subject: dict[str, str] | None = Depends(get_optional_subject),
) -> StreamingResponse:
    session_id = payload.session_id or f"ses_{uuid4().hex[:12]}"
    message_id = f"msg_{uuid4().hex[:12]}"
    request_id = getattr(request.state, "request_id", "") or request_id_ctx.get() or "unknown"
    rag_service = request.app.state.rag_service
    session_service = SessionService(session)
    username = subject["username"] if subject else None

    log_event(
        logger,
        "INFO",
        "chat.stream.started",
        request_id=request_id,
        session_id=session_id,
        message_id=message_id,
        input_summary=summarize_user_text(payload.message),
    )

    async def _event_stream():
        first_packet_logged = False
        done_sent = False
        persisted_session_id = session_id
        assistant_content_parts: list[str] = []
        final_trace: dict | None = None
        try:
            if username:
                chat_session = await session_service.ensure_chat_session(
                    username=username,
                    session_id=payload.session_id,
                    opening_message=payload.message,
                    create_if_missing=True,
                )
                persisted_session_id = chat_session.id
                await session_service.add_chat_message(
                    session_id=chat_session.id,
                    role="user",
                    content=payload.message,
                )

            yield (
                "event: meta\n"
                f"data: {json.dumps({'request_id': request_id, 'session_id': persisted_session_id, 'message_id': message_id})}\n\n"
            )
            if not first_packet_logged:
                first_packet_logged = True
                log_event(
                    logger,
                    "INFO",
                    "chat.stream.first_packet",
                    request_id=request_id,
                    session_id=persisted_session_id,
                    message_id=message_id,
                )

            stream = rag_service.stream_answer(
                message=payload.message,
                session_id=persisted_session_id,
                request_id=request_id,
                message_id=message_id,
                user_id=username,
            )
            async with asyncio.timeout(10.0):
                async for event_name, data in stream:
                    if event_name == "content":
                        assistant_content_parts.append(str(data.get("delta", "")))
                    elif event_name == "trace":
                        final_trace = data
                    yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

            if username:
                await session_service.add_chat_message(
                    session_id=persisted_session_id,
                    role="assistant",
                    content="".join(assistant_content_parts),
                    rag_trace=final_trace,
                )
                await session.commit()

            yield f"event: done\ndata: {json.dumps('[DONE]')}\n\n"
            done_sent = True
            log_event(
                logger,
                "INFO",
                "chat.stream.completed",
                request_id=request_id,
                session_id=persisted_session_id,
                message_id=message_id,
            )
        except AppError as exc:
            payload_error = {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "request_id": request_id,
            }
            await session.rollback()
            yield f"event: error\ndata: {json.dumps(payload_error)}\n\n"
            if not done_sent:
                yield f"event: done\ndata: {json.dumps('[DONE]')}\n\n"
            log_event(
                logger,
                "ERROR",
                "chat.stream.failed",
                request_id=request_id,
                session_id=persisted_session_id,
                message_id=message_id,
                error_code=exc.code,
            )
        except asyncio.CancelledError:
            await session.rollback()
            log_event(
                logger,
                "WARN",
                "chat.stream.interrupted",
                request_id=request_id,
                session_id=persisted_session_id,
                message_id=message_id,
                error_code="CHAT_STREAM_INTERRUPTED",
            )
            raise
        except Exception:
            await session.rollback()
            payload_error = {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "detail": None,
                "request_id": request_id,
            }
            yield f"event: error\ndata: {json.dumps(payload_error)}\n\n"
            if not done_sent:
                yield f"event: done\ndata: {json.dumps('[DONE]')}\n\n"
            log_event(
                logger,
                "ERROR",
                "chat.stream.failed",
                request_id=request_id,
                session_id=persisted_session_id,
                message_id=message_id,
                error_code="INTERNAL_ERROR",
            )

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
