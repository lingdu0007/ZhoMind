from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.repositories import RetrievalRepository
from src.infrastructure.retrieval.bm25_store import Bm25Store
from src.infrastructure.retrieval.vector_store import MilvusVectorStore


@dataclass
class RetrievalIndexSyncService:
    session_factory: Callable[[], AsyncSession]
    vector_store: MilvusVectorStore
    bm25_store: Bm25Store

    async def rebuild_document_index(self, document_id: str, version: int) -> dict:
        async with self.session_factory() as session:
            repo = RetrievalRepository(session)
            chunks = await repo.list_chunks_for_index(document_id=document_id, version=version)
            if not chunks:
                return {"document_id": document_id, "version": version, "chunks": 0}

            chunk_ids = [c["chunk_id"] for c in chunks]
            await repo.mark_chunks_index_status(chunk_ids, index_status="indexing")

            self.vector_store.upsert(chunks)
            self.bm25_store.upsert(chunks)

            indexed_count = await repo.mark_chunks_index_status(
                chunk_ids,
                index_status="indexed",
                indexed_at=datetime.now(UTC),
            )
            await session.commit()
            return {"document_id": document_id, "version": version, "chunks": indexed_count}

    async def replace_and_rebuild_document_chunks(
        self,
        document_id: str,
        chunks: list[dict],
        version: int = 1,
    ) -> dict:
        async with self.session_factory() as session:
            repo = RetrievalRepository(session)
            chunk_ids = await repo.replace_document_chunks(document_id=document_id, chunks=chunks, version=version)
            await repo.mark_chunks_index_status(chunk_ids, index_status="indexing")

            indexed_chunks = await repo.list_chunks_for_index(document_id=document_id, version=version)
            self.vector_store.upsert(indexed_chunks)
            self.bm25_store.upsert(indexed_chunks)

            indexed_count = await repo.mark_chunks_index_status(
                chunk_ids,
                index_status="indexed",
                indexed_at=datetime.now(UTC),
            )
            await session.commit()
            return {
                "document_id": document_id,
                "version": version,
                "chunks": indexed_count,
            }

    async def delete_document_index(self, document_id: str, version: int | None = None) -> dict:
        vector_deleted = self.vector_store.delete_document(document_id=document_id, version=version)
        bm25_deleted = self.bm25_store.delete_document(document_id=document_id, version=version)

        async with self.session_factory() as session:
            repo = RetrievalRepository(session)
            db_cleanup = await repo.delete_document_retrieval_data(document_id=document_id)
            await session.commit()

        return {
            "document_id": document_id,
            "version": version,
            "vector_deleted": vector_deleted,
            "bm25_deleted": bm25_deleted,
            "db_chunks_deleted": db_cleanup["chunks_deleted"],
            "db_postings_deleted": db_cleanup["bm25_deleted"],
        }
