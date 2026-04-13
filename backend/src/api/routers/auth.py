from fastapi import APIRouter

from src.shared.exceptions import NotImplementedErrorApp

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register() -> dict:
    raise NotImplementedErrorApp()


@router.post("/login")
async def login() -> dict:
    raise NotImplementedErrorApp()


@router.get("/me")
async def me() -> dict:
    raise NotImplementedErrorApp()
