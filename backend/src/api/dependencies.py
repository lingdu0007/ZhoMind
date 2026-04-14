from collections.abc import AsyncGenerator

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.auth.service import AuthService
from src.infrastructure.auth.bearer import decode_bearer_subject, parse_bearer_token
from src.shared.exceptions import AppError, AuthError
from src.shared.request_context import user_id_ctx


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async for session in request.app.state.db.session():
        yield session


async def get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(session)


async def get_current_subject(
    token: str = Depends(parse_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    subject = decode_bearer_subject(token, service)
    user_id_ctx.set(subject["username"])
    return subject


async def get_optional_subject(
    authorization: str | None = Header(default=None),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str] | None:
    if authorization is None:
        return None
    try:
        token = await parse_bearer_token(authorization)
        subject = decode_bearer_subject(token, service)
    except AuthError:
        return None
    user_id_ctx.set(subject["username"])
    return subject


async def require_admin(subject: dict[str, str] = Depends(get_current_subject)) -> dict[str, str]:
    if subject.get("role") != "admin":
        raise AppError("AUTH_FORBIDDEN", "Forbidden", status_code=403)
    return subject
