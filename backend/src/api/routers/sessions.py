import logging

from fastapi import APIRouter, Response

from src.infrastructure.logging.observability import log_event
from src.shared.exceptions import AppError
from src.shared.schemas import ListResponse, PaginationMeta

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


@router.get("", response_model=ListResponse)
async def list_sessions() -> ListResponse:
    log_event(logger, "INFO", "sessions.list.succeeded")
    return ListResponse(items=[], pagination=PaginationMeta())


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    if session_id.startswith("missing"):
        log_event(
            logger,
            "WARN",
            "sessions.get.failed",
            session_id=session_id,
            error_code="RESOURCE_NOT_FOUND",
        )
        raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
    log_event(logger, "INFO", "sessions.get.succeeded", session_id=session_id)
    return {
        "session_id": session_id,
        "items": [],
    }


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    if session_id.startswith("missing"):
        log_event(
            logger,
            "WARN",
            "sessions.delete.failed",
            session_id=session_id,
            error_code="RESOURCE_NOT_FOUND",
        )
        raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
    log_event(logger, "INFO", "sessions.delete.succeeded", session_id=session_id)
    return Response(status_code=204)
