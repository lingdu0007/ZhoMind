from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.errors import register_exception_handlers
from src.api.router import api_router
from src.application.document_service import DocumentService, DocumentTaskExecutor
from src.infrastructure.config.settings import get_settings
from src.infrastructure.db.connection import create_database
from src.infrastructure.logging.logger import setup_logging
from src.infrastructure.queue.runner import QueueRunner
from src.shared.middleware import RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    setup_logging(settings.log_level)

    db = create_database(settings.database_url)
    await db.connect()

    queue_runner = QueueRunner(settings.queue_backend, executor=DocumentTaskExecutor(service=None))
    document_service = DocumentService(queue_runner=queue_runner)
    queue_runner.executor = DocumentTaskExecutor(service=document_service)
    await queue_runner.start()

    app.state.db = db
    app.state.queue_runner = queue_runner
    app.state.document_service = document_service

    yield

    await queue_runner.stop()
    await db.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ZhoMind API",
        version="1.0.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict:
        return {"status": "ready"}

    app.include_router(api_router, prefix=settings.api_prefix)

    return app
