from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.db.models import DocumentJobModel, DocumentModel, MessageModel, SessionModel, UserModel
from src.infrastructure.db.repositories import DocumentJobRepository, MessageRepository, SessionRepository


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
                    "AND name IN ('users','sessions','messages','documents','document_jobs')"
                )
            )
            tables = {name for (name,) in tables_result.all()}
            assert tables == {"users", "sessions", "messages", "documents", "document_jobs"}

            user = UserModel(username="u1", password_hash="hash", role="user")
            session.add(user)
            await session.flush()

            session_repo = SessionRepository(session)
            message_repo = MessageRepository(session)
            job_repo = DocumentJobRepository(session)

            created_session = await session_repo.create_session(user_id=user.id, title="t1")
            assert created_session["session_id"].startswith("ses_")
            assert created_session["message_count"] == 0

            created_message = await message_repo.create_message(
                session_id=created_session["session_id"],
                role="user",
                content="hello",
                rag_trace={"trace": 1},
            )
            assert created_message["message_id"].startswith("msg_")
            assert created_message["role"] == "user"

            queried_session = await session_repo.get_session(created_session["session_id"])
            assert queried_session is not None
            assert queried_session["message_count"] == 1

            document = DocumentModel(
                document_id="doc_001",
                filename="demo.txt",
                file_type="text/plain",
                file_size=5,
                status="pending",
                chunk_strategy="general",
            )
            session.add(document)

            job = DocumentJobModel(
                job_id="job_001",
                document_id="doc_001",
                status="queued",
                stage="uploaded",
                progress=0,
            )
            session.add(job)
            await session.commit()

            jobs, total = await job_repo.list_jobs(page=1, page_size=20, status="queued")
            assert total == 1
            assert jobs[0]["job_id"] == "job_001"
            assert jobs[0]["status"] == "queued"

            updated = await job_repo.update_job_status(
                job_id="job_001",
                status="running",
                stage="parsing",
                progress=25,
                message="Parsing document",
            )
            assert updated is True
            await session.commit()

            fetched_job = await job_repo.get_job("job_001")
            assert fetched_job is not None
            assert fetched_job["status"] == "running"
            assert fetched_job["stage"] == "parsing"
            assert fetched_job["progress"] == 25

            finished = datetime.now(UTC)
            updated = await job_repo.update_job_status(
                job_id="job_001",
                status="succeeded",
                stage="completed",
                progress=100,
                message="done",
                finished_at=finished,
            )
            assert updated is True
            await session.commit()

            fetched_job = await job_repo.get_job("job_001")
            assert fetched_job is not None
            assert fetched_job["status"] == "succeeded"
            assert fetched_job["stage"] == "completed"
            assert fetched_job["progress"] == 100
            assert fetched_job["finished_at"] is not None

            deleted = await session_repo.delete_session(created_session["session_id"])
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
            session.add(UserModel(username="u2", password_hash="hash", role="user"))
            session.add(
                DocumentModel(
                    document_id="doc_002",
                    filename="enum.txt",
                    file_type="text/plain",
                    file_size=1,
                    status="pending",
                    chunk_strategy="general",
                )
            )
            await session.commit()

            session.add(
                DocumentJobModel(
                    job_id="job_bad",
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
