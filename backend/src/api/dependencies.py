from fastapi import Depends

from backend.src.infrastructure.auth.bearer import parse_bearer_token, permission_hook


async def get_current_subject(token: str = Depends(parse_bearer_token)) -> dict:
    return await permission_hook(token)
