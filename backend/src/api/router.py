from fastapi import APIRouter

from src.api.routers import auth, chat, document_jobs, documents, sessions

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(sessions.router)
api_router.include_router(chat.router)
api_router.include_router(documents.router)
api_router.include_router(document_jobs.router)
