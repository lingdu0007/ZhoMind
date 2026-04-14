from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.config.settings import Settings


@dataclass(frozen=True)
class RetrievalTuning:
    dense_weight: float
    sparse_weight: float
    bm25_min_term_match: int
    bm25_min_score: float
    dense_top_k: int
    sparse_top_k: int
    dense_rescue_enabled: bool
    max_document_filter_count: int
    max_context_tokens: int
    chunk_version_retention: int
    max_chunk_count_per_document: int
    max_bm25_postings_per_document: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "RetrievalTuning":
        dense_weight = settings.rag_dense_weight
        sparse_weight = settings.rag_sparse_weight
        total = dense_weight + sparse_weight
        if total <= 0:
            dense_weight, sparse_weight = 0.55, 0.45
        else:
            dense_weight /= total
            sparse_weight /= total

        return cls(
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            bm25_min_term_match=settings.rag_bm25_min_term_match,
            bm25_min_score=settings.rag_bm25_min_score,
            dense_top_k=settings.rag_dense_top_k,
            sparse_top_k=settings.rag_sparse_top_k,
            dense_rescue_enabled=settings.rag_dense_rescue_enabled,
            max_document_filter_count=settings.rag_max_document_filter_count,
            max_context_tokens=settings.rag_max_context_tokens,
            chunk_version_retention=settings.rag_chunk_version_retention,
            max_chunk_count_per_document=settings.rag_max_chunk_count_per_document,
            max_bm25_postings_per_document=settings.rag_max_bm25_postings_per_document,
        )
