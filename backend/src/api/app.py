from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.errors import register_exception_handlers
from src.api.router import api_router
from src.infrastructure.config.settings import get_settings
from src.infrastructure.db.connection import create_database
from src.infrastructure.logging.logger import setup_logging
from src.infrastructure.queue.runner import QueueRunner, TaskExecutor
from src.shared.middleware import RequestIdMiddleware


class NoopTaskExecutor(TaskExecutor):
    async def execute(self, task_name: str, payload: dict) -> None:
        _ = task_name, payload
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    setup_logging(settings.log_level)

    db = create_database(settings.database_url)
    await db.connect()

    queue_runner = QueueRunner(settings.queue_backend, NoopTaskExecutor())
    await queue_runner.start()

    app.state.db = db
    app.state.queue_runner = queue_runner

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
