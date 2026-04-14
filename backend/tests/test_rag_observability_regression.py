import logging

from src.application.rag_service import RagService


class _ExplodingRetrievalService:
    async def retrieve(self, query: str, *, user_id: str, document_ids=None, version=None):
        _ = (query, user_id, document_ids, version)
        raise RuntimeError("boom")


class _UnusedDocumentService:
    async def hybrid_retrieve(self, query: str, top_k: int = 8):
        _ = (query, top_k)
        return []


def _make_rag_service() -> RagService:
    return RagService(
        document_service=_UnusedDocumentService(),
        retrieval_service=_ExplodingRetrievalService(),
    )


def test_rag_answer_failure_log_includes_bound_session_and_user(caplog) -> None:
    service = _make_rag_service()

    with caplog.at_level(logging.ERROR):
        try:
            import asyncio

            asyncio.run(
                service.answer(
                    message="hello",
                    session_id="session_obs_answer_001",
                    request_id="req_obs_answer_001",
                    user_id="obs_user_answer",
                )
            )
        except Exception:
            pass

    record = next(item for item in caplog.records if item.getMessage() == "rag.answer.failed")
    assert record.request_id == "req_obs_answer_001"
    assert record.session_id == "session_obs_answer_001"
    assert record.user_id == "obs_user_answer"
    assert record.error_code == "RAG_UPSTREAM_ERROR"


def test_rag_stream_failure_log_includes_bound_session_and_user(caplog) -> None:
    service = _make_rag_service()

    with caplog.at_level(logging.ERROR):
        try:
            import asyncio

            async def _run() -> None:
                async for _event in service.stream_answer(
                    message="hello",
                    session_id="session_obs_stream_001",
                    request_id="req_obs_stream_001",
                    message_id="msg_obs_stream_001",
                    user_id="obs_user_stream",
                ):
                    pass

            asyncio.run(_run())
        except Exception:
            pass

    record = next(item for item in caplog.records if item.getMessage() == "rag.stream.failed")
    assert record.request_id == "req_obs_stream_001"
    assert record.session_id == "session_obs_stream_001"
    assert record.user_id == "obs_user_stream"
    assert record.error_code == "RAG_UPSTREAM_ERROR"
