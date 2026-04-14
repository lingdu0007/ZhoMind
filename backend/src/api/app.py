import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.errors import register_exception_handlers
from src.api.router import api_router
from src.application.document_service import DocumentService, DocumentTaskExecutor
from src.application.rag_service import RagService
from src.application.retrieval.service import RetrievalService
from src.infrastructure.config.settings import get_settings
from src.infrastructure.db.connection import create_database
from src.infrastructure.db.models import Base
from src.infrastructure.logging.logger import setup_logging
from src.infrastructure.queue.runner import QueueRunner
from src.infrastructure.retrieval.bm25_store import Bm25Store
from src.infrastructure.retrieval.vector_store import MilvusVectorStore
from src.infrastructure.storage.local_storage import LocalStorage
from src.shared.middleware import RequestIdMiddleware

try:
    from src.infrastructure.retrieval.index_sync import RetrievalIndexSyncService
except ImportError:  # pragma: no cover
    RetrievalIndexSyncService = None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    setup_logging(level=settings.log_level, service=settings.app_name, env=settings.env)

    db = create_database(settings.database_url)
    await db.connect()
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    queue_runner = QueueRunner(settings.queue_backend, executor=DocumentTaskExecutor(service=None))
    vector_store = MilvusVectorStore(
        host=settings.milvus_host,
        port=settings.milvus_port,
        collection_name=settings.milvus_collection_name,
    )
    bm25_store = Bm25Store()
    index_sync_service = None
    if RetrievalIndexSyncService is not None:
        try:
            index_sync_service = RetrievalIndexSyncService(
                session_factory=db.session_factory,
                vector_store=vector_store,
                bm25_store=bm25_store,
            )
        except Exception:
            logger.exception("retrieval.index_sync.unavailable")

    document_service = DocumentService(
        queue_runner=queue_runner,
        vector_store=vector_store,
        bm25_store=bm25_store,
        index_sync_service=index_sync_service,
        storage=LocalStorage(settings.document_storage_dir),
    )
    retrieval_service = RetrievalService(
        vector_store=vector_store,
        bm25_store=bm25_store,
        top_k=settings.rag_retrieval_top_k,
    )
    queue_runner.executor = DocumentTaskExecutor(service=document_service)
    await queue_runner.start()

    app.state.db = db
    app.state.queue_runner = queue_runner
    app.state.document_service = document_service
    app.state.rag_service = RagService(
        document_service=document_service,
        retrieval_service=retrieval_service,
        min_score=settings.rag_min_score,
        min_hits=settings.rag_min_hits,
        max_context_chunks=settings.rag_max_context_chunks,
        score_low=settings.rag_score_low,
        score_high=settings.rag_score_high,
        retrieval_top_k=settings.rag_retrieval_top_k,
        bm25_min_term_match=settings.rag_bm25_min_term_match,
        bm25_min_score=settings.rag_bm25_min_score,
    )

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
