import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator
from uuid import uuid4

from src.application.interfaces.retrieval import RetrievalPort
from src.infrastructure.logging.observability import bind_context, log_event
from src.shared.exceptions import AppError

logger = logging.getLogger(__name__)


@dataclass
class RagResult:
    session_id: str
    message_id: str
    content: str
    rag_trace: dict


class RagService:
    def __init__(
        self,
        document_service,
        min_score: float = 0.25,
        min_hits: int = 1,
        max_context_chunks: int = 3,
        score_low: float = 0.18,
        score_high: float = 0.32,
        retrieval_top_k: int = 8,
        bm25_min_term_match: int = 1,
        bm25_min_score: float = 0.05,
        retrieval_service: RetrievalPort | None = None,
    ) -> None:
        self._document_service = document_service
        self._retrieval_service = retrieval_service
        self._min_score = min_score
        self._min_hits = min_hits
        self._max_context_chunks = max_context_chunks
        self._score_low = score_low
        self._score_high = score_high
        self._retrieval_top_k = retrieval_top_k
        self._bm25_min_term_match = bm25_min_term_match
        self._bm25_min_score = bm25_min_score

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _gate(
        self,
        ranked: list[dict],
        top1_score: float,
        lexical_hits: int,
        dense_hits: int,
    ) -> tuple[bool, str]:
        if top1_score < self._score_low:
            return False, "low_reject"
        if top1_score >= self._score_high:
            return True, "high_accept"

        fallback_pass = lexical_hits >= 1 or dense_hits >= 1
        return fallback_pass, "mid_fallback_accept" if fallback_pass else "mid_fallback_reject"

    async def _retrieve(self, query: str, user_id: str) -> tuple[list[dict], dict, dict]:
        start = time.perf_counter()
        if self._retrieval_service is not None:
            retrieval_result = await self._retrieval_service.retrieve(query, user_id=user_id)
            ranked = retrieval_result.chunks
            retrieval_trace = retrieval_result.trace
        else:
            ranked = await self._document_service.hybrid_retrieve(query, top_k=self._retrieval_top_k)
            retrieval_trace = {
                "retrieval": {
                    "query": query,
                    "user_id": user_id,
                    "top_k": self._retrieval_top_k,
                    "document_ids": [],
                    "version": None,
                    "dense_hit_count": len(ranked),
                    "sparse_hit_count": len(ranked),
                },
                "rerank": {
                    "strategy": "score_sort",
                    "weights": {"dense": 1.0, "sparse": 0.0},
                    "selected_chunk_ids": [item["chunk_id"] for item in ranked],
                },
                "relevance": {
                    "hit_count": len(ranked),
                    "has_hits": bool(ranked),
                    "best_score": ranked[0].get("score", 0.0) if ranked else 0.0,
                },
                "generation": {
                    "mode": "extractive_stub",
                    "context_chunk_count": len(ranked),
                },
            }

        top1_score = float(ranked[0]["score"]) if ranked else 0.0
        valid_hits = sum(1 for item in ranked if float(item.get("score", 0.0)) >= self._min_score)
        lexical_hits = sum(
            1
            for item in ranked
            if float(item.get("sparse_score", 0.0)) >= self._bm25_min_score
            and float(item.get("sparse_score", 0.0)) > 0
        )
        dense_hits = sum(1 for item in ranked if float(item.get("dense_score", 0.0)) > 0)

        gate_passed, gate_reason = self._gate(ranked, top1_score, lexical_hits, dense_hits)
        min_hits_passed = valid_hits >= self._min_hits
        hit_gate_passed = gate_passed and min_hits_passed

        selected = ranked[: self._max_context_chunks] if hit_gate_passed else []

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics = {
            "retrieval_hits": len(selected),
            "retrieval_hit_rate": 1.0 if selected else 0.0,
            "retrieval_latency_ms": latency_ms,
            "top1_score": round(top1_score, 6),
            "valid_hits": valid_hits,
            "lexical_hits": lexical_hits,
            "dense_hits": dense_hits,
            "gate_passed": hit_gate_passed,
            "gate_reason": gate_reason,
            "min_score": self._min_score,
            "min_hits": self._min_hits,
            "score_low": self._score_low,
            "score_high": self._score_high,
            "retrieval_top_k": self._retrieval_top_k,
            "bm25_min_term_match": self._bm25_min_term_match,
            "bm25_min_score": self._bm25_min_score,
        }

        retrieval_trace["relevance"]["filtered_hit_count"] = valid_hits
        retrieval_trace["relevance"]["context_hit_count"] = len(selected)
        retrieval_trace["relevance"]["gate_passed"] = hit_gate_passed
        retrieval_trace["relevance"]["gate_reason"] = gate_reason
        retrieval_trace["generation"]["context_chunk_count"] = len(selected)

        if not hit_gate_passed:
            log_event(
                logger,
                "INFO",
                "rag.retrieve.gated",
                top1_score=metrics["top1_score"],
                valid_hits=valid_hits,
                lexical_hits=lexical_hits,
                dense_hits=dense_hits,
                gate_reason=gate_reason,
                score_low=self._score_low,
                score_high=self._score_high,
                min_hits=self._min_hits,
            )

        return selected, metrics, retrieval_trace

    async def _rerank(self, candidates: list[dict]) -> tuple[list[dict], dict]:
        start = time.perf_counter()
        reranked = sorted(candidates, key=lambda x: x.get("score", 0.0), reverse=True)[: self._max_context_chunks]
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return reranked, {"rerank_latency_ms": latency_ms}

    async def _generate(self, query: str, contexts: list[dict]) -> tuple[str, dict]:
        start = time.perf_counter()
        await asyncio.sleep(0)

        if not contexts:
            content = "未检索到足够相关的知识片段，请补充更具体的问题或关键词。"
        else:
            joined = " | ".join(item["content"] for item in contexts)
            content = f"Based on retrieved context: {joined}. Answer: {query}"

        in_tokens = max(1, len(query) // 4)
        out_tokens = max(1, len(content) // 4)
        cost = round(in_tokens * 0.000001 + out_tokens * 0.000002, 8)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return content, {
            "generation_latency_ms": latency_ms,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "estimated_cost": cost,
        }

    def _build_trace(
        self,
        request_id: str,
        session_id: str,
        message_id: str,
        contexts: list[dict],
        metrics: dict,
        retrieval_trace: dict,
    ) -> dict:
        trace = {
            "request_id": request_id,
            "session_id": session_id,
            "message_id": message_id,
            "retrieved": [
                {
                    "document_id": x["document_id"],
                    "chunk_id": x["chunk_id"],
                    "score": x.get("score", 0.0),
                }
                for x in contexts
            ],
            "metrics": metrics,
        }
        trace.update(retrieval_trace)
        return trace

    @staticmethod
    def _normalize_message(message: str) -> str:
        return message.strip()

    async def answer(self, message: str, session_id: str, request_id: str, user_id: str | None = None) -> RagResult:
        normalized_message = self._normalize_message(message)
        total_start = time.perf_counter()
        message_id = f"msg_{uuid4().hex[:12]}"
        retrieval_user_id = user_id or session_id
        try:
            with bind_context(session_id=session_id, user_id=retrieval_user_id):
                retrieved, retrieval_metrics, retrieval_trace = await self._retrieve(normalized_message, retrieval_user_id)
                reranked, rerank_metrics = await self._rerank(retrieved)
                content, generation_metrics = await self._generate(normalized_message, reranked)

                total_latency = round((time.perf_counter() - total_start) * 1000, 2)
                metrics = {
                    **retrieval_metrics,
                    **rerank_metrics,
                    **generation_metrics,
                    "total_latency_ms": total_latency,
                    "failure_rate": 0.0,
                }
                rag_trace = self._build_trace(request_id, session_id, message_id, reranked, metrics, retrieval_trace)
                return RagResult(session_id=session_id, message_id=message_id, content=content, rag_trace=rag_trace)
        except AppError:
            raise
        except Exception as exc:  # pragma: no cover
            log_event(
                logger,
                "ERROR",
                "rag.answer.failed",
                request_id=request_id,
                session_id=session_id,
                user_id=retrieval_user_id,
                message_id=message_id,
                error_code="RAG_UPSTREAM_ERROR",
                error=str(exc),
            )
            raise AppError("RAG_UPSTREAM_ERROR", "RAG upstream error", status_code=500) from exc

    async def stream_answer(
        self,
        message: str,
        session_id: str,
        request_id: str,
        message_id: str,
        user_id: str | None = None,
    ) -> AsyncIterator[tuple[str, dict]]:
        normalized_message = self._normalize_message(message)
        total_start = time.perf_counter()
        retrieval_user_id = user_id or session_id
        try:
            with bind_context(session_id=session_id, user_id=retrieval_user_id):
                retrieved, retrieval_metrics, retrieval_trace = await self._retrieve(normalized_message, retrieval_user_id)
                yield "rag_step", {"step": "retrieve", "detail": retrieval_metrics}

                reranked, rerank_metrics = await self._rerank(retrieved)
                yield "rag_step", {"step": "rerank", "detail": rerank_metrics}

                content, generation_metrics = await self._generate(normalized_message, reranked)
                yield "rag_step", {"step": "generate", "detail": generation_metrics}

                first_packet_emitted = False
                first_packet_ms = 0.0
                for part in content.split(" "):
                    if not part:
                        continue
                    if not first_packet_emitted:
                        first_packet_emitted = True
                        first_packet_ms = round((time.perf_counter() - total_start) * 1000, 2)
                    yield "content", {"delta": part + " "}

                total_latency = round((time.perf_counter() - total_start) * 1000, 2)
                metrics = {
                    **retrieval_metrics,
                    **rerank_metrics,
                    **generation_metrics,
                    "first_packet_latency_ms": first_packet_ms if first_packet_emitted else total_latency,
                    "total_latency_ms": total_latency,
                    "failure_rate": 0.0,
                }
                yield "trace", self._build_trace(request_id, session_id, message_id, reranked, metrics, retrieval_trace)
        except AppError:
            raise
        except Exception as exc:  # pragma: no cover
            log_event(
                logger,
                "ERROR",
                "rag.stream.failed",
                request_id=request_id,
                session_id=session_id,
                user_id=retrieval_user_id,
                message_id=message_id,
                error_code="RAG_UPSTREAM_ERROR",
                error=str(exc),
            )
            raise AppError("RAG_UPSTREAM_ERROR", "RAG upstream error", status_code=500) from exc
