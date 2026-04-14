import logging

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_auth_service, get_current_subject
from src.application.auth.service import AuthService
from src.infrastructure.logging.observability import log_event
from src.shared.schemas.auth import AuthResponse, CurrentUserResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    response = await service.register(payload)
    log_event(logger, "INFO", "auth.register.succeeded", user_id=response.username, role=response.role)
    return response


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    response = await service.login(payload)
    log_event(logger, "INFO", "auth.login.succeeded", user_id=response.username, role=response.role)
    return response


@router.get("/me", response_model=CurrentUserResponse, status_code=status.HTTP_200_OK)
async def me(subject: dict[str, str] = Depends(get_current_subject)) -> CurrentUserResponse:
    log_event(logger, "INFO", "auth.me.succeeded", user_id=subject["username"], role=subject["role"])
    return CurrentUserResponse(username=subject["username"], role=subject["role"])
