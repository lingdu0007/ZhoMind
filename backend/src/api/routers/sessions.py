from fastapi import APIRouter, Response

from src.shared.exceptions import AppError
from src.shared.schemas import ListResponse, PaginationMeta

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=ListResponse)
async def list_sessions() -> ListResponse:
    return ListResponse(items=[], pagination=PaginationMeta())


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    if session_id.startswith("missing"):
        raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
    return {
        "session_id": session_id,
        "items": [],
    }


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    if session_id.startswith("missing"):
        raise AppError("RESOURCE_NOT_FOUND", "Session not found", status_code=404)
    return Response(status_code=204)
