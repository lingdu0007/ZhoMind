import logging

from fastapi import APIRouter, Body, Depends, Request, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_subject
from src.infrastructure.logging.observability import log_event
from src.shared.exceptions import AppError

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = "user"
    admin_code: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthTokens(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    username: str
    role: str


class CurrentUser(BaseModel):
    username: str
    role: str


def _build_token(username: str, role: str) -> AuthTokens:
    token = "admin-token" if role == "admin" else "user-token"
    return AuthTokens(
        access_token=token,
        token_type="Bearer",
        expires_in=3600,
        refresh_token=None,
        username=username,
        role=role,
    )


@router.post("/register", response_model=AuthTokens, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest = Body(...)) -> AuthTokens:
    if payload.role not in {"admin", "user"}:
        log_event(
            logger,
            "WARN",
            "auth.register.failed",
            user_id=payload.username,
            error_code="VALIDATION_ERROR",
            reason="invalid_role",
        )
        raise AppError("VALIDATION_ERROR", "Invalid role", detail={"role": payload.role}, status_code=422)

    if payload.username in {"admin", "user"}:
        log_event(
            logger,
            "WARN",
            "auth.register.failed",
            user_id=payload.username,
            error_code="RESOURCE_CONFLICT",
            reason="username_exists",
        )
        raise AppError("RESOURCE_CONFLICT", "Username already exists", status_code=409)

    if payload.role == "admin" and payload.admin_code != "admin-invite-code":
        log_event(
            logger,
            "WARN",
            "auth.register.failed",
            user_id=payload.username,
            error_code="AUTH_FORBIDDEN",
            reason="invalid_admin_code",
        )
        raise AppError("AUTH_FORBIDDEN", "Forbidden", status_code=403)

    log_event(logger, "INFO", "auth.register.succeeded", user_id=payload.username, role=payload.role)
    return _build_token(payload.username, payload.role)


@router.post("/login", response_model=AuthTokens)
async def login(payload: LoginRequest = Body(...)) -> AuthTokens:
    credentials = {
        "admin": {"password": "admin-token", "role": "admin"},
        "user": {"password": "user-token", "role": "user"},
    }
    item = credentials.get(payload.username)
    if not item or item["password"] != payload.password:
        log_event(
            logger,
            "WARN",
            "auth.login.failed",
            user_id=payload.username,
            error_code="AUTH_BAD_CREDENTIALS",
        )
        raise AppError("AUTH_BAD_CREDENTIALS", "Invalid username or password", status_code=401)

    log_event(logger, "INFO", "auth.login.succeeded", user_id=payload.username, role=item["role"])
    return _build_token(payload.username, item["role"])


@router.get("/me", response_model=CurrentUser)
async def me(request: Request, subject: dict = Depends(get_current_subject)) -> CurrentUser:
    _ = request
    role = subject.get("role", "user")
    username = subject.get("token", "user") if role == "user" else "admin"
    log_event(logger, "INFO", "auth.me.succeeded", user_id=subject.get("username", "unknown"), role=role)
    return CurrentUser(username=username, role=role)
