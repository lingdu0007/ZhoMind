from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.db.models import DocumentModel, UserModel
from src.infrastructure.db.repositories import RetrievalRepository
from src.infrastructure.retrieval.bm25_store import Bm25Store
from src.infrastructure.retrieval.index_sync import RetrievalIndexSyncService
from src.infrastructure.retrieval.vector_store import MilvusVectorStore


def _upgrade_to_head(db_url: str) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")


def test_index_sync_rebuild_and_delete(tmp_path: Path) -> None:
    db_path = tmp_path / "sync.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _upgrade_to_head(db_url)

    async def _run() -> None:
        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        vector_store = MilvusVectorStore(host="127.0.0.1", port=19530, collection_name="test_collection")
        bm25_store = Bm25Store()
        sync = RetrievalIndexSyncService(session_factory=session_factory, vector_store=vector_store, bm25_store=bm25_store)

        async with session_factory() as session:
            session.add(UserModel(username="u1", password_hash="hash", role="user"))
            session.add(
                DocumentModel(
                    document_id="doc_sync",
                    filename="sync.txt",
                    file_type="text/plain",
                    file_size=12,
                    status="processing",
                    chunk_strategy="general",
                )
            )
            await session.commit()

            repo = RetrievalRepository(session)
            await repo.replace_document_chunks(
                document_id="doc_sync",
                version=1,
                chunks=[
                    {"chunk_index": 0, "content": "alpha beta", "keywords": ["alpha"], "generated_questions": ["what alpha"], "metadata": {}},
                    {"chunk_index": 1, "content": "beta gamma", "keywords": ["beta"], "generated_questions": ["what beta"], "metadata": {}},
                ],
            )
            await session.commit()

        rebuilt = await sync.rebuild_document_index("doc_sync", version=1)
        assert rebuilt["chunks"] == 2

        deleted = await sync.delete_document_index("doc_sync", version=1)
        assert deleted["db_chunks_deleted"] >= 0
        assert deleted["db_postings_deleted"] >= 0

        await engine.dispose()

    import asyncio

    asyncio.run(_run())
