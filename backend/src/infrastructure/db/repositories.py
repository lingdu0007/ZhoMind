from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    Bm25PostingModel,
    DocumentChunkModel,
    DocumentJobModel,
    MessageModel,
    SessionModel,
)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def _tokenize(text: str) -> list[str]:
    return [token.strip().lower() for token in text.split() if token.strip()]


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
        return bool(result.rowcount and result.rowcount > 0)

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


@dataclass
class RetrievalRepository:
    session: AsyncSession

    async def replace_document_chunks(self, document_id: str, chunks: list[dict], version: int) -> list[str]:
        await self.session.execute(
            delete(Bm25PostingModel).where(
                and_(Bm25PostingModel.document_id == document_id, Bm25PostingModel.version == version)
            )
        )
        await self.session.execute(
            delete(DocumentChunkModel).where(
                and_(DocumentChunkModel.document_id == document_id, DocumentChunkModel.version == version)
            )
        )

        chunk_ids: list[str] = []
        for item in chunks:
            chunk_id = item.get("chunk_id") or f"chk_{uuid4().hex[:12]}"
            retrieval_text = item.get("retrieval_text") or self._build_retrieval_text(item)
            model = DocumentChunkModel(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=item["chunk_index"],
                content=item["content"],
                keywords=item.get("keywords", []),
                generated_questions=item.get("generated_questions", []),
                chunk_metadata=item.get("metadata"),
                retrieval_text=retrieval_text,
                tokens=_tokenize(retrieval_text),
                version=version,
                index_status="pending",
            )
            self.session.add(model)
            chunk_ids.append(chunk_id)

            term_counts = Counter(_tokenize(retrieval_text))
            doc_len = sum(term_counts.values()) or 1
            for term, tf in term_counts.items():
                posting = Bm25PostingModel(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    term=term[:128],
                    tf=tf,
                    doc_len=doc_len,
                    version=version,
                )
                self.session.add(posting)

        await self.session.flush()
        return chunk_ids

    async def mark_chunks_index_status(
        self,
        chunk_ids: list[str],
        index_status: str,
        indexed_at: datetime | None = None,
    ) -> int:
        values = {"index_status": index_status, "updated_at": datetime.now(UTC)}
        if indexed_at is not None:
            values["indexed_at"] = indexed_at

        result = await self.session.execute(
            update(DocumentChunkModel).where(DocumentChunkModel.chunk_id.in_(chunk_ids)).values(**values)
        )
        return int(result.rowcount or 0)

    async def list_chunks_for_index(self, document_id: str, version: int) -> list[dict]:
        rows = (
            await self.session.execute(
                select(DocumentChunkModel)
                .where(
                    and_(
                        DocumentChunkModel.document_id == document_id,
                        DocumentChunkModel.version == version,
                    )
                )
                .order_by(DocumentChunkModel.chunk_index.asc())
            )
        ).scalars().all()

        items: list[dict] = []
        for row in rows:
            items.append(
                {
                    "chunk_id": row.chunk_id,
                    "document_id": row.document_id,
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "retrieval_text": row.retrieval_text,
                    "version": row.version,
                }
            )
        return items

    async def delete_document_retrieval_data(self, document_id: str) -> dict:
        postings = await self.session.execute(
            delete(Bm25PostingModel).where(Bm25PostingModel.document_id == document_id)
        )
        chunks = await self.session.execute(
            delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
        return {
            "bm25_deleted": int(postings.rowcount or 0),
            "chunks_deleted": int(chunks.rowcount or 0),
        }

    @staticmethod
    def _build_retrieval_text(item: dict) -> str:
        parts: list[str] = [item.get("content", "")]
        parts.extend(item.get("keywords", []))
        parts.extend(item.get("generated_questions", []))
        return " ".join(part for part in parts if part).strip()
