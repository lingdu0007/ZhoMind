from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import DocumentStatus, JobStatus
from src.infrastructure.db.models import (
    ChatMessageModel,
    ChatSessionModel,
    DocumentChunkModel,
    DocumentModel,
    IngestionJobModel,
    UserModel,
)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def _tokenize(text: str) -> list[str]:
    return [token.strip().lower() for token in text.split() if token.strip()]


@dataclass
class UserRepository:
    session: AsyncSession

    async def get_by_username(self, *, username: str) -> UserModel | None:
        return await self.session.scalar(select(UserModel).where(UserModel.username == username))

    async def create_user(self, *, username: str, password_hash: str, role: str) -> UserModel:
        model = UserModel(
            id=f"user_{uuid4().hex[:12]}",
            username=username,
            password_hash=password_hash,
            role=role,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

@dataclass
class ChatSessionRepository:
    session: AsyncSession

    async def create_session(
        self,
        *,
        user_id: str,
        title: str | None = None,
        session_id: str | None = None,
    ) -> ChatSessionModel:
        model = ChatSessionModel(id=session_id or f"session_{uuid4().hex[:12]}", user_id=user_id, title=title)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def list_sessions(self, *, user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[ChatSessionModel], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(ChatSessionModel).where(ChatSessionModel.user_id == user_id)
        )
        rows = (
            await self.session.execute(
                select(ChatSessionModel)
                .where(ChatSessionModel.user_id == user_id)
                .order_by(desc(ChatSessionModel.updated_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

    async def get_session(self, *, session_id: str) -> ChatSessionModel | None:
        return await self.session.scalar(select(ChatSessionModel).where(ChatSessionModel.id == session_id))

    async def get_session_for_user(self, *, user_id: str, session_id: str) -> ChatSessionModel | None:
        return await self.session.scalar(
            select(ChatSessionModel).where(
                ChatSessionModel.id == session_id,
                ChatSessionModel.user_id == user_id,
            )
        )

    async def delete_session_for_user(self, *, user_id: str, session_id: str) -> bool:
        result = await self.session.execute(
            delete(ChatSessionModel).where(
                ChatSessionModel.id == session_id,
                ChatSessionModel.user_id == user_id,
            )
        )
        return bool(result.rowcount and result.rowcount > 0)


@dataclass
class ChatMessageRepository:
    session: AsyncSession

    async def add_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        rag_trace_json: dict | None = None,
    ) -> ChatMessageModel:
        model = ChatMessageModel(
            id=f"message_{uuid4().hex[:12]}",
            session_id=session_id,
            role=role,
            content=content,
            rag_trace_json=rag_trace_json,
        )
        self.session.add(model)
        await self.session.execute(
            update(ChatSessionModel)
            .where(ChatSessionModel.id == session_id)
            .values(
                message_count=ChatSessionModel.message_count + 1,
                updated_at=datetime.now(UTC),
            )
        )
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def list_messages_for_session(self, *, session_id: str) -> list[ChatMessageModel]:
        rows = (
            await self.session.execute(
                select(ChatMessageModel)
                .where(ChatMessageModel.session_id == session_id)
                .order_by(ChatMessageModel.created_at.asc())
            )
        ).scalars().all()
        return list(rows)


@dataclass
class DocumentRepository:
    session: AsyncSession

    async def create_document(self, *, filename: str, chunk_strategy: str | None = None) -> DocumentModel:
        model = DocumentModel(
            id=f"document_{uuid4().hex[:12]}",
            filename=filename,
            status=DocumentStatus.UPLOADED.value,
            chunk_strategy=chunk_strategy,
            chunk_count=0,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def update_status(self, *, document_id: str, status: DocumentStatus, chunk_count: int | None = None) -> bool:
        values: dict[str, object] = {"status": status.value, "updated_at": datetime.now(UTC)}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        result = await self.session.execute(
            update(DocumentModel).where(DocumentModel.id == document_id).values(**values)
        )
        return bool(result.rowcount and result.rowcount > 0)


@dataclass
class IngestionJobRepository:
    session: AsyncSession

    async def create_job(self, *, document_id: str, stage: str = "uploaded") -> IngestionJobModel:
        model = IngestionJobModel(
            id=f"job_{uuid4().hex[:12]}",
            document_id=document_id,
            status=JobStatus.QUEUED.value,
            stage=stage,
            progress=0,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def get_job(self, *, job_id: str) -> IngestionJobModel | None:
        return await self.session.scalar(select(IngestionJobModel).where(IngestionJobModel.id == job_id))

    async def update_job(
        self,
        *,
        job_id: str,
        status: JobStatus,
        stage: str,
        progress: int,
        message: str | None = None,
    ) -> bool:
        result = await self.session.execute(
            update(IngestionJobModel)
            .where(IngestionJobModel.id == job_id)
            .values(
                status=status.value,
                stage=stage,
                progress=progress,
                message=message,
                updated_at=datetime.now(UTC),
            )
        )
        return bool(result.rowcount and result.rowcount > 0)


@dataclass
class RetrievalRepository:
    session: AsyncSession

    async def replace_document_chunks(self, *, document_id: str, chunks: list[dict], version: int) -> list[str]:
        await self.session.execute(delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id))

        chunk_ids: list[str] = []
        for item in chunks:
            chunk_id = item.get("chunk_id") or f"chunk_{uuid4().hex[:12]}"
            retrieval_text = item.get("retrieval_text") or self._build_retrieval_text(item)
            metadata = dict(item.get("metadata") or {})
            metadata.update(
                {
                    "version": version,
                    "retrieval_text": retrieval_text,
                    "keywords": list(item.get("keywords") or []),
                    "generated_questions": list(item.get("generated_questions") or []),
                    "index_status": "pending",
                    "indexed_at": None,
                    "token_count": sum(Counter(_tokenize(retrieval_text)).values()),
                }
            )
            model = DocumentChunkModel(
                id=chunk_id,
                document_id=document_id,
                chunk_index=int(item["chunk_index"]),
                content=item["content"],
                chunk_metadata_json=metadata,
            )
            self.session.add(model)
            chunk_ids.append(chunk_id)

        await self.session.flush()
        return chunk_ids

    async def mark_chunks_index_status(
        self,
        chunk_ids: list[str],
        index_status: str,
        indexed_at: datetime | None = None,
    ) -> int:
        if not chunk_ids:
            return 0

        rows = (
            await self.session.execute(select(DocumentChunkModel).where(DocumentChunkModel.id.in_(chunk_ids)))
        ).scalars().all()
        indexed_at_value = _iso(indexed_at) if indexed_at is not None else None
        for row in rows:
            metadata = dict(row.chunk_metadata_json or {})
            metadata["index_status"] = index_status
            if indexed_at is not None:
                metadata["indexed_at"] = indexed_at_value
            row.chunk_metadata_json = metadata
        await self.session.flush()
        return len(rows)

    async def list_chunks_for_index(self, *, document_id: str, version: int) -> list[dict]:
        rows = (
            await self.session.execute(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.document_id == document_id)
                .order_by(DocumentChunkModel.chunk_index.asc())
            )
        ).scalars().all()

        items: list[dict] = []
        for row in rows:
            metadata = dict(row.chunk_metadata_json or {})
            row_version = int(metadata.get("version", 1))
            if row_version != version:
                continue
            items.append(
                {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "retrieval_text": metadata.get("retrieval_text") or row.content,
                    "version": row_version,
                }
            )
        return items

    async def delete_document_retrieval_data(self, *, document_id: str) -> dict:
        chunks = await self.session.execute(
            delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
        return {
            "bm25_deleted": 0,
            "chunks_deleted": int(chunks.rowcount or 0),
        }

    @staticmethod
    def _build_retrieval_text(item: dict) -> str:
        parts: list[str] = [item.get("content", "")]
        parts.extend(item.get("keywords", []))
        parts.extend(item.get("generated_questions", []))
        return " ".join(part for part in parts if part).strip()


SessionRepository = ChatSessionRepository
MessageRepository = ChatMessageRepository
DocumentJobRepository = IngestionJobRepository
