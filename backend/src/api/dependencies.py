from fastapi import Depends

from src.infrastructure.auth.bearer import parse_bearer_token, permission_hook
from src.shared.request_context import user_id_ctx


async def get_current_subject(token: str = Depends(parse_bearer_token)) -> dict:
    subject = await permission_hook(token)
    user_id_ctx.set(subject.get("username", ""))
    return subject
