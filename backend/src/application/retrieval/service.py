from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.application.interfaces.retrieval import RetrievalPort, RetrievalResult


@dataclass
class _Candidate:
    chunk_id: str
    payload: dict[str, Any]
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float = 0.0
    sparse_score: float = 0.0


class RetrievalService(RetrievalPort):
    def __init__(
        self,
        *,
        vector_store: Any,
        bm25_store: Any,
        top_k: int = 5,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        rrf_k: int = 60,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._top_k = top_k
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        document_ids: list[str] | None = None,
        version: int | None = None,
    ) -> RetrievalResult:
        dense_hits = self._vector_store.query(
            query,
            top_k=self._top_k,
            document_ids=document_ids,
            version=version,
        )
        sparse_hits = self._bm25_store.query(
            query,
            top_k=self._top_k,
            document_ids=document_ids,
            version=version,
        )

        ranked = self._merge_and_rank(dense_hits=dense_hits, sparse_hits=sparse_hits)
        selected = ranked[: self._top_k]

        trace = {
            "retrieval": {
                "query": query,
                "user_id": user_id,
                "top_k": self._top_k,
                "document_ids": document_ids or [],
                "version": version,
                "dense_hit_count": len(dense_hits),
                "sparse_hit_count": len(sparse_hits),
            },
            "rerank": {
                "strategy": "weighted_rrf",
                "weights": {
                    "dense": self._dense_weight,
                    "sparse": self._sparse_weight,
                },
                "selected_chunk_ids": [item["chunk_id"] for item in selected],
            },
            "relevance": {
                "hit_count": len(selected),
                "has_hits": bool(selected),
                "best_score": selected[0]["score"] if selected else 0.0,
            },
            "generation": {
                "mode": "extractive_stub",
                "context_chunk_count": len(selected),
            },
        }

        return RetrievalResult(chunks=selected, trace=trace)

    def _merge_and_rank(
        self,
        *,
        dense_hits: list[dict[str, Any]],
        sparse_hits: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: dict[str, _Candidate] = {}

        for rank, item in enumerate(dense_hits, start=1):
            chunk_id = str(item["chunk_id"])
            candidate = candidates.setdefault(
                chunk_id,
                _Candidate(chunk_id=chunk_id, payload=dict(item)),
            )
            candidate.payload.update(item)
            candidate.dense_rank = rank
            candidate.dense_score = float(item.get("dense_score") or item.get("score") or 0.0)

        for rank, item in enumerate(sparse_hits, start=1):
            chunk_id = str(item["chunk_id"])
            candidate = candidates.setdefault(
                chunk_id,
                _Candidate(chunk_id=chunk_id, payload=dict(item)),
            )
            for key, value in item.items():
                candidate.payload.setdefault(key, value)
            candidate.sparse_rank = rank
            candidate.sparse_score = float(item.get("sparse_score") or item.get("score") or 0.0)

        merged: list[dict[str, Any]] = []
        for candidate in candidates.values():
            dense_rrf = 0.0
            sparse_rrf = 0.0

            if candidate.dense_rank is not None:
                dense_rrf = self._dense_weight / (self._rrf_k + candidate.dense_rank)
            if candidate.sparse_rank is not None:
                sparse_rrf = self._sparse_weight / (self._rrf_k + candidate.sparse_rank)

            dense_score = max(0.0, min(1.0, candidate.dense_score))
            sparse_score = max(0.0, min(1.0, candidate.sparse_score))
            fused_score = dense_score * self._dense_weight + sparse_score * self._sparse_weight
            if sparse_score > 0:
                fused_score = max(fused_score, sparse_score * self._sparse_weight)

            payload = dict(candidate.payload)
            payload["score"] = round(fused_score, 6)
            payload["dense_score"] = candidate.dense_score
            payload["sparse_score"] = candidate.sparse_score
            payload["dense_rank_score"] = round(dense_rrf, 6)
            payload["sparse_rank_score"] = round(sparse_rrf, 6)
            merged.append(payload)

        return sorted(
            merged,
            key=lambda item: (
                float(item.get("score") or 0.0),
                float(item.get("dense_rank_score") or 0.0) + float(item.get("sparse_rank_score") or 0.0),
            ),
            reverse=True,
        )
