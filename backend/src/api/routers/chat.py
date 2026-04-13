import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None


@router.post("")
async def chat(payload: ChatRequest) -> dict:
    session_id = payload.session_id or f"ses_{uuid4().hex[:12]}"
    return {
        "session_id": session_id,
        "message": {
            "message_id": f"msg_{uuid4().hex[:12]}",
            "role": "assistant",
            "content": f"Echo: {payload.message}",
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "rag_trace": None,
        },
    }


@router.post("/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    session_id = payload.session_id or f"ses_{uuid4().hex[:12]}"
    message_id = f"msg_{uuid4().hex[:12]}"

    async def _event_stream():
        yield (
            "event: meta\n"
            f"data: {json.dumps({'request_id': 'req_stream', 'session_id': session_id, 'message_id': message_id})}\n\n"
        )
        yield f"event: content\ndata: {json.dumps({'delta': 'Echo: '})}\n\n"
        yield f"event: content\ndata: {json.dumps({'delta': payload.message})}\n\n"
        yield f"event: done\ndata: {json.dumps('[DONE]')}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
