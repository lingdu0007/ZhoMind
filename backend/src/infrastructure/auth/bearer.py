from fastapi import Header

from src.shared.exceptions import AuthError


async def parse_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if authorization is None:
        raise AuthError(code="AUTH_MISSING_TOKEN", message="Missing bearer token")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthError(code="AUTH_INVALID_TOKEN", message="Invalid or expired token")

    return parts[1].strip()


async def permission_hook(token: str) -> dict:
    return {"token": token, "role": "unknown"}
