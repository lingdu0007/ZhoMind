import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.infrastructure.logging.observability import log_event, summarize_user_text
from src.shared.exceptions import AppError
from src.shared.request_context import request_id_ctx

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = None


@router.post("")
async def chat(payload: ChatRequest, request: Request) -> dict:
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

    rag_service = request.app.state.rag_service
    result = await asyncio.wait_for(
        rag_service.answer(message=payload.message, session_id=session_id, request_id=request_id),
        timeout=10.0,
    )
    if isinstance(result, dict):
        session_id = result.get("session_id", session_id)
        message_data = result.get("message", {})
        response = {
            "session_id": session_id,
            "message": {
                "message_id": message_data.get("message_id", f"msg_{uuid4().hex[:12]}"),
                "role": message_data.get("role", "assistant"),
                "content": message_data.get("content", ""),
                "timestamp": message_data.get("timestamp", datetime.now(UTC).isoformat().replace("+00:00", "Z")),
                "rag_trace": message_data.get("rag_trace"),
            },
        }
    else:
        response = {
            "session_id": result.session_id,
            "message": {
                "message_id": result.message_id,
                "role": "assistant",
                "content": result.content,
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "rag_trace": result.rag_trace,
            },
        }

    completed_message_id = response["message"]["message_id"]
    log_event(
        logger,
        "INFO",
        "chat.request.completed",
        request_id=request_id,
        session_id=session_id,
        message_id=completed_message_id,
    )
    return response


@router.post("/stream")
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    session_id = payload.session_id or f"ses_{uuid4().hex[:12]}"
    message_id = f"msg_{uuid4().hex[:12]}"
    request_id = getattr(request.state, "request_id", "") or request_id_ctx.get() or "unknown"
    rag_service = request.app.state.rag_service

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
        try:
            yield (
                "event: meta\n"
                f"data: {json.dumps({'request_id': request_id, 'session_id': session_id, 'message_id': message_id})}\n\n"
            )
            if not first_packet_logged:
                first_packet_logged = True
                log_event(
                    logger,
                    "INFO",
                    "chat.stream.first_packet",
                    request_id=request_id,
                    session_id=session_id,
                    message_id=message_id,
                )

            stream = rag_service.stream_answer(
                message=payload.message,
                session_id=session_id,
                request_id=request_id,
                message_id=message_id,
            )
            async with asyncio.timeout(10.0):
                async for event_name, data in stream:
                    yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

            yield f"event: done\ndata: {json.dumps('[DONE]')}\n\n"
            done_sent = True
            log_event(
                logger,
                "INFO",
                "chat.stream.completed",
                request_id=request_id,
                session_id=session_id,
                message_id=message_id,
            )
        except AppError as exc:
            payload_error = {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
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
                session_id=session_id,
                message_id=message_id,
                error_code=exc.code,
            )
        except asyncio.CancelledError:
            log_event(
                logger,
                "WARN",
                "chat.stream.interrupted",
                request_id=request_id,
                session_id=session_id,
                message_id=message_id,
                error_code="CHAT_STREAM_INTERRUPTED",
            )
            raise
        except Exception:
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
                session_id=session_id,
                message_id=message_id,
                error_code="INTERNAL_ERROR",
            )

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
