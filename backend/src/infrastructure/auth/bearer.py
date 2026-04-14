import logging

from fastapi import Header

from src.infrastructure.logging.observability import log_event, redact_headers
from src.shared.exceptions import AuthError

logger = logging.getLogger(__name__)


async def parse_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if authorization is None:
        log_event(
            logger,
            "WARN",
            "auth.token.parse_failed",
            error_code="AUTH_INVALID_TOKEN",
            reason="missing_authorization_header",
        )
        raise AuthError(code="AUTH_INVALID_TOKEN", message="Invalid or expired token")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        log_event(
            logger,
            "WARN",
            "auth.token.parse_failed",
            error_code="AUTH_INVALID_TOKEN",
            reason="malformed_authorization_header",
            headers=redact_headers({"authorization": authorization}),
        )
        raise AuthError(code="AUTH_INVALID_TOKEN", message="Invalid or expired token")

    return parts[1].strip()


async def permission_hook(token: str) -> dict:
    if token == "admin-token":
        subject = {"token": token, "role": "admin", "username": "admin"}
    else:
        subject = {"token": token, "role": "user", "username": "user"}
    log_event(logger, "DEBUG", "auth.subject.resolved", user_id=subject["username"], role=subject["role"])
    return subject
