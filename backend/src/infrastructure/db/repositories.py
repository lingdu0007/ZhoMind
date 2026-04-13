from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DocumentJobModel, MessageModel, SessionModel


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


@dataclass
class SessionRepository:
    session: AsyncSession

    async def create_session(self, user_id: int, title: str | None = None) -> dict:
        model = SessionModel(session_id=f"ses_{uuid4().hex[:12]}", user_id=user_id, title=title)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return {
            "session_id": model.session_id,
            "title": model.title,
            "updated_at": _iso(model.updated_at),
            "message_count": model.message_count,
        }

    async def list_sessions(self, user_id: int, page: int, page_size: int) -> tuple[list[dict], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(SessionModel).where(SessionModel.user_id == user_id)
        )
        stmt = (
            select(SessionModel)
            .where(SessionModel.user_id == user_id)
            .order_by(desc(SessionModel.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [
            {
                "session_id": row.session_id,
                "title": row.title,
                "updated_at": _iso(row.updated_at),
                "message_count": row.message_count,
            }
            for row in rows
        ]
        return items, int(total or 0)

    async def get_session(self, session_id: str) -> dict | None:
        row = await self.session.scalar(select(SessionModel).where(SessionModel.session_id == session_id))
        if row is None:
            return None
        return {
            "session_id": row.session_id,
            "title": row.title,
            "updated_at": _iso(row.updated_at),
            "message_count": row.message_count,
        }

    async def delete_session(self, session_id: str) -> bool:
        row = await self.session.scalar(select(SessionModel).where(SessionModel.session_id == session_id))
        if row is None:
            return False
        await self.session.delete(row)
        return True


@dataclass
class MessageRepository:
    session: AsyncSession

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        rag_trace: dict | None = None,
    ) -> dict:
        model = MessageModel(
            message_id=f"msg_{uuid4().hex[:12]}",
            session_id=session_id,
            role=role,
            content=content,
            rag_trace=rag_trace,
        )
        self.session.add(model)

        await self.session.execute(
            update(SessionModel)
            .where(SessionModel.session_id == session_id)
            .values(
                message_count=SessionModel.message_count + 1,
                updated_at=datetime.now(UTC),
            )
        )

        await self.session.flush()
        await self.session.refresh(model)

        return {
            "message_id": model.message_id,
            "role": model.role,
            "content": model.content,
            "timestamp": _iso(model.timestamp),
            "rag_trace": model.rag_trace,
        }


@dataclass
class DocumentJobRepository:
    session: AsyncSession

    async def list_jobs(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        document_id: str | None = None,
    ) -> tuple[list[dict], int]:
        filters = []
        if status:
            filters.append(DocumentJobModel.status == status)
        if document_id:
            filters.append(DocumentJobModel.document_id == document_id)

        where_clause = and_(*filters) if filters else None

        count_stmt = select(func.count()).select_from(DocumentJobModel)
        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)

        total = await self.session.scalar(count_stmt)

        stmt = select(DocumentJobModel)
        if where_clause is not None:
            stmt = stmt.where(where_clause)

        stmt = stmt.order_by(desc(DocumentJobModel.created_at)).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()

        return [self._to_dict(row) for row in rows], int(total or 0)

    async def get_job(self, job_id: str) -> dict | None:
        row = await self.session.scalar(select(DocumentJobModel).where(DocumentJobModel.job_id == job_id))
        if row is None:
            return None
        return self._to_dict(row)

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        stage: str,
        progress: int,
        message: str | None = None,
        error_code: str | None = None,
        finished_at: datetime | None = None,
    ) -> bool:
        result = await self.session.execute(
            update(DocumentJobModel)
            .where(DocumentJobModel.job_id == job_id)
            .values(
                status=status,
                stage=stage,
                progress=progress,
                message=message,
                error_code=error_code,
                updated_at=datetime.now(UTC),
                finished_at=finished_at,
            )
        )
        return result.rowcount > 0

    def _to_dict(self, row: DocumentJobModel) -> dict:
        return {
            "job_id": row.job_id,
            "document_id": row.document_id,
            "status": row.status,
            "stage": row.stage,
            "progress": row.progress,
            "message": row.message,
            "error_code": row.error_code,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
            "finished_at": _iso(row.finished_at),
        }
