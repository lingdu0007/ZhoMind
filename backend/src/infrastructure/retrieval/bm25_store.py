from __future__ import annotations

from collections import Counter
from typing import Any

from src.application.retrieval_utils import bm25_scores


def _tokenize(text: str) -> list[str]:
    return [token.strip().lower() for token in text.split() if token.strip()]


class Bm25Store:
    """In-memory BM25 store; persistence handled by DB repository."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}

    def upsert(self, chunks: list[dict[str, Any]]) -> None:
        for chunk in chunks:
            content = chunk.get("retrieval_text") or chunk.get("content", "")
            tokens = _tokenize(content)
            term_counts = Counter(tokens)
            self._rows[chunk["chunk_id"]] = {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "content": content,
                "version": int(chunk.get("version", 1)),
                "term_counts": dict(term_counts),
            }

    def delete_document(self, document_id: str, version: int | None = None) -> int:
        keys = [
            chunk_id
            for chunk_id, row in self._rows.items()
            if row["document_id"] == document_id and (version is None or row["version"] == version)
        ]
        for chunk_id in keys:
            self._rows.pop(chunk_id, None)
        return len(keys)

    def query(self, query: str, top_k: int = 10, document_ids: list[str] | None = None, version: int | None = None) -> list[dict[str, Any]]:
        pool = []
        for row in self._rows.values():
            if document_ids and row["document_id"] not in document_ids:
                continue
            if version is not None and row["version"] != version:
                continue
            pool.append(
                {
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "content": row["content"],
                }
            )

        ranked = bm25_scores(query, pool)
        items: list[dict[str, Any]] = []
        for item, score in ranked[:top_k]:
            items.append(
                {
                    "chunk_id": item["chunk_id"],
                    "document_id": item["document_id"],
                    "content": item["content"],
                    "sparse_score": round(score, 6),
                }
            )
        return items
