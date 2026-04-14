from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from src.domain.enums import JobStatus
from src.infrastructure.db.models import DocumentModel, IngestionJobModel, UserModel
from src.infrastructure.db.repositories import (
    DocumentJobRepository,
    MessageRepository,
    RetrievalRepository,
    SessionRepository,
)


def _upgrade_to_head(db_url: str) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")


def test_db_migration_and_repository_crud(tmp_path: Path) -> None:
    db_path = tmp_path / "integration.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _upgrade_to_head(db_url)

    async def _run() -> None:
        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            tables_result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('users','chat_sessions','chat_messages','documents','ingestion_jobs','document_chunks')"
                )
            )
            tables = {name for (name,) in tables_result.all()}
            assert tables == {
                "users",
                "chat_sessions",
                "chat_messages",
                "documents",
                "ingestion_jobs",
                "document_chunks",
            }

            user = UserModel(id="user_001", username="u1", password_hash="hash", role="user")
            session.add(user)
            await session.flush()

            session_repo = SessionRepository(session)
            message_repo = MessageRepository(session)
            job_repo = DocumentJobRepository(session)

            created_session = await session_repo.create_session(user_id=user.id, title="t1")
            assert created_session.id.startswith("session_")
            assert created_session.message_count == 0

            created_message = await message_repo.add_message(
                session_id=created_session.id,
                role="user",
                content="hello",
                rag_trace_json={"trace": 1},
            )
            assert created_message.id.startswith("message_")
            assert created_message.role == "user"

            queried_session = await session_repo.get_session(session_id=created_session.id)
            assert queried_session is not None
            assert queried_session.message_count == 1

            document = DocumentModel(
                id="doc_001",
                filename="demo.txt",
                status="uploaded",
                chunk_strategy="general",
                chunk_count=0,
            )
            session.add(document)
            await session.flush()

            job = await job_repo.create_job(document_id=document.id, stage="uploaded")
            assert job.id.startswith("job_")
            assert job.status == "queued"
            await session.commit()

            updated = await job_repo.update_job(
                job_id=job.id,
                status=JobStatus.RUNNING,
                stage="parsing",
                progress=25,
                message="Parsing document",
            )
            assert updated is True
            await session.commit()

            fetched_job = await job_repo.get_job(job_id=job.id)
            assert fetched_job is not None
            assert fetched_job.status == "running"
            assert fetched_job.stage == "parsing"
            assert fetched_job.progress == 25

            updated = await job_repo.update_job(
                job_id=job.id,
                status=JobStatus.SUCCEEDED,
                stage="completed",
                progress=100,
                message="done",
            )
            assert updated is True
            await session.commit()

            fetched_job = await job_repo.get_job(job_id=job.id)
            assert fetched_job is not None
            assert fetched_job.status == "succeeded"
            assert fetched_job.stage == "completed"
            assert fetched_job.progress == 100

            deleted = await session_repo.delete_session_for_user(
                user_id=user.id,
                session_id=created_session.id,
            )
            assert deleted is True
            await session.commit()

        await engine.dispose()

    import asyncio

    asyncio.run(_run())


def test_job_enum_drift_protection_by_db_constraints(tmp_path: Path) -> None:
    db_path = tmp_path / "enum_guard.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _upgrade_to_head(db_url)

    async def _run() -> None:
        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            session.add(UserModel(id="user_002", username="u2", password_hash="hash", role="user"))
            session.add(
                DocumentModel(
                    id="doc_002",
                    filename="enum.txt",
                    status="uploaded",
                    chunk_strategy="general",
                    chunk_count=0,
                )
            )
            await session.commit()

            session.add(
                IngestionJobModel(
                    id="job_bad",
                    document_id="doc_002",
                    status="bad_status",
                    stage="uploaded",
                    progress=0,
                )
            )

            failed = False
            try:
                await session.commit()
            except Exception:
                failed = True
                await session.rollback()

            assert failed is True

        await engine.dispose()

    import asyncio

    asyncio.run(_run())


def test_retrieval_repository_persistence_and_sync(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    _upgrade_to_head(db_url)

    async def _run() -> None:
        engine = create_async_engine(db_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            session.add(UserModel(id="user_003", username="u3", password_hash="hash", role="user"))
            session.add(
                DocumentModel(
                    id="doc_003",
                    filename="retrieval.txt",
                    status="uploaded",
                    chunk_strategy="general",
                    chunk_count=0,
                )
            )
            await session.commit()

            repo = RetrievalRepository(session)
            chunk_ids = await repo.replace_document_chunks(
                document_id="doc_003",
                version=2,
                chunks=[
                    {
                        "chunk_index": 0,
                        "content": "alpha beta",
                        "keywords": ["alpha"],
                        "generated_questions": ["what is alpha"],
                        "metadata": {"source": "unit"},
                    },
                    {
                        "chunk_index": 1,
                        "content": "beta gamma",
                        "keywords": ["beta"],
                        "generated_questions": ["what is beta"],
                        "metadata": {"source": "unit"},
                    },
                ],
            )
            assert len(chunk_ids) == 2

            listed = await repo.list_chunks_for_index(document_id="doc_003", version=2)
            assert len(listed) == 2
            assert listed[0]["chunk_index"] == 0
            assert listed[1]["chunk_index"] == 1

            marked = await repo.mark_chunks_index_status(
                chunk_ids,
                index_status="indexed",
                indexed_at=datetime.now(UTC),
            )
            assert marked == 2
            await session.commit()

            indexed_rows = await session.execute(
                text("SELECT metadata_json FROM document_chunks WHERE document_id = 'doc_003'")
            )
            metadata_rows = [json.loads(row[0]) for row in indexed_rows.all()]
            assert all(item is not None for item in metadata_rows)
            assert all(item["index_status"] == "indexed" for item in metadata_rows)

            cleanup = await repo.delete_document_retrieval_data(document_id="doc_003")
            assert cleanup["chunks_deleted"] == 2
            assert cleanup["bm25_deleted"] == 0
            await session.commit()

        await engine.dispose()

    import asyncio

    asyncio.run(_run())
