from fastapi import APIRouter

from src.shared.schemas import ListResponse, PaginationMeta

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=ListResponse)
async def list_sessions() -> ListResponse:
    return ListResponse(items=[], pagination=PaginationMeta())


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "title": None,
        "updated_at": None,
        "message_count": 0,
    }
