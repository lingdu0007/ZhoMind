import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_subject, get_db_session
from src.application.sessions.service import SessionService
from src.infrastructure.logging.observability import log_event
from src.shared.schemas.sessions import SessionDetailResponse, SessionListResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


async def get_session_service(session: AsyncSession = Depends(get_db_session)) -> SessionService:
    return SessionService(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    subject: dict[str, str] = Depends(get_current_subject),
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    response = await service.list_sessions(username=subject["username"])
    log_event(logger, "INFO", "sessions.list.succeeded", user_id=subject["username"], total=len(response.items))
    return response


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    subject: dict[str, str] = Depends(get_current_subject),
    service: SessionService = Depends(get_session_service),
) -> SessionDetailResponse:
    response = await service.get_session_detail(username=subject["username"], session_id=session_id)
    log_event(logger, "INFO", "sessions.get.succeeded", user_id=subject["username"], session_id=session_id)
    return response


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    subject: dict[str, str] = Depends(get_current_subject),
    service: SessionService = Depends(get_session_service),
) -> Response:
    await service.delete_session(username=subject["username"], session_id=session_id)
    log_event(logger, "INFO", "sessions.delete.succeeded", user_id=subject["username"], session_id=session_id)
    return Response(status_code=204)
