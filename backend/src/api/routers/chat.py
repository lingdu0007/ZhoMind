from fastapi import APIRouter

from src.shared.exceptions import NotImplementedErrorApp

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat() -> dict:
    raise NotImplementedErrorApp()


@router.get("/stream")
async def chat_stream() -> dict:
    raise NotImplementedErrorApp()
