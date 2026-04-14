import asyncio

from src.application.retrieval.service import RetrievalService
from src.infrastructure.retrieval.bm25_store import Bm25Store
from src.infrastructure.retrieval.vector_store import MilvusVectorStore


async def _build_service() -> RetrievalService:
    vector_store = MilvusVectorStore(host="127.0.0.1", port=19530, collection_name="test_retrieval_trace")
    bm25_store = Bm25Store()
    chunks = [
        {
            "chunk_id": "chk_trace_001",
            "document_id": "doc_trace_001",
            "chunk_index": 0,
            "content": "System architecture uses FastAPI services with retrieval and ranking.",
            "retrieval_text": "System architecture uses FastAPI services with retrieval and ranking.",
            "version": 1,
        },
        {
            "chunk_id": "chk_trace_002",
            "document_id": "doc_trace_001",
            "chunk_index": 1,
            "content": "The backend includes document chunking and indexing workflows.",
            "retrieval_text": "The backend includes document chunking and indexing workflows.",
            "version": 1,
        },
    ]
    vector_store.upsert(chunks)
    bm25_store.upsert(chunks)
    return RetrievalService(vector_store=vector_store, bm25_store=bm25_store)


def test_retrieval_trace_contains_required_sections() -> None:
    async def _run() -> None:
        service = await _build_service()
        result = await service.retrieve("What is the architecture?", user_id="u1")
        assert result.chunks
        assert set(result.trace.keys()) >= {"retrieval", "rerank", "relevance", "generation"}
        assert result.trace["retrieval"]["query"] == "What is the architecture?"
        assert result.trace["generation"]["mode"] == "extractive_stub"

    asyncio.run(_run())
