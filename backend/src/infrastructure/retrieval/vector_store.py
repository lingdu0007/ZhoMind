from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from src.application.retrieval_utils import embed_text

try:  # pragma: no cover
    from pymilvus import (  # type: ignore
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )

    _MILVUS_AVAILABLE = True
except Exception:  # pragma: no cover
    Collection = None
    CollectionSchema = None
    DataType = None
    FieldSchema = None
    connections = None
    utility = None
    _MILVUS_AVAILABLE = False


class MilvusVectorStore:
    """Dense vector store with Milvus fallback to in-memory rows."""

    def __init__(
        self,
        host: str,
        port: int,
        collection_name: str,
        dim: int = 64,
    ) -> None:
        self._dim = dim
        self._collection_name = collection_name
        self._memory_rows: dict[str, dict[str, Any]] = {}
        self._collection = None

        if _MILVUS_AVAILABLE:
            connections.connect(alias="default", host=host, port=str(port))
            if not utility.has_collection(collection_name):
                schema = CollectionSchema(
                    fields=[
                        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
                        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=128),
                        FieldSchema(name="chunk_index", dtype=DataType.INT64),
                        FieldSchema(name="version", dtype=DataType.INT64),
                        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
                    ],
                    description="zhomind dense chunk vectors v1",
                )
                collection = Collection(name=collection_name, schema=schema)
                collection.create_index(
                    field_name="embedding",
                    index_params={
                        "metric_type": "IP",
                        "index_type": "HNSW",
                        "params": {"M": 16, "efConstruction": 200},
                    },
                )
            self._collection = Collection(name=collection_name)
            self._collection.load()

    def upsert(self, chunks: Iterable[dict[str, Any]]) -> None:
        chunk_list = list(chunks)
        if not chunk_list:
            return

        if self._collection is None:
            for chunk in chunk_list:
                vector = chunk.get("embedding") or embed_text(chunk["content"], dim=self._dim)
                self._memory_rows[chunk["chunk_id"]] = {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "chunk_index": int(chunk.get("chunk_index", 0)),
                    "version": int(chunk.get("version", 1)),
                    "content": chunk["content"],
                    "embedding": vector,
                }
            return

        rows_chunk_id = [row["chunk_id"] for row in chunk_list]
        rows_doc_id = [row["document_id"] for row in chunk_list]
        rows_chunk_index = [int(row.get("chunk_index", 0)) for row in chunk_list]
        rows_version = [int(row.get("version", 1)) for row in chunk_list]
        rows_content = [row["content"][:65535] for row in chunk_list]
        rows_vec = [row.get("embedding") or embed_text(row["content"], dim=self._dim) for row in chunk_list]
        self._collection.upsert([rows_chunk_id, rows_doc_id, rows_chunk_index, rows_version, rows_content, rows_vec])
        self._collection.flush()

    def delete_document(self, document_id: str, version: int | None = None) -> int:
        if self._collection is None:
            keys = [
                chunk_id
                for chunk_id, row in self._memory_rows.items()
                if row["document_id"] == document_id and (version is None or row["version"] == version)
            ]
            for chunk_id in keys:
                self._memory_rows.pop(chunk_id, None)
            return len(keys)

        expr = f'document_id == "{document_id}"'
        if version is not None:
            expr += f" and version == {version}"
        result = self._collection.delete(expr)
        self._collection.flush()
        return int(getattr(result, "delete_count", 0) or 0)

    def query(self, query: str, top_k: int = 10, document_ids: list[str] | None = None, version: int | None = None) -> list[dict[str, Any]]:
        query_vec = embed_text(query, dim=self._dim)

        if self._collection is None:
            scored = []
            for row in self._memory_rows.values():
                if document_ids and row["document_id"] not in document_ids:
                    continue
                if version is not None and row["version"] != version:
                    continue
                score = _dot(query_vec, row["embedding"])
                scored.append(
                    {
                        "chunk_id": row["chunk_id"],
                        "document_id": row["document_id"],
                        "chunk_index": row["chunk_index"],
                        "version": row["version"],
                        "content": row["content"],
                        "dense_score": round(score, 6),
                    }
                )
            scored.sort(key=lambda item: item["dense_score"], reverse=True)
            return scored[:top_k]

        expr_parts: list[str] = []
        if document_ids:
            quoted = ", ".join(f'"{doc_id}"' for doc_id in document_ids)
            expr_parts.append(f"document_id in [{quoted}]")
        if version is not None:
            expr_parts.append(f"version == {version}")
        expr = " and ".join(expr_parts) if expr_parts else None

        search_results = self._collection.search(
            data=[query_vec],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "document_id", "chunk_index", "version", "content"],
        )

        items: list[dict[str, Any]] = []
        for hit in search_results[0]:
            entity = hit.entity
            items.append(
                {
                    "chunk_id": entity.get("chunk_id"),
                    "document_id": entity.get("document_id"),
                    "chunk_index": entity.get("chunk_index"),
                    "version": entity.get("version"),
                    "content": entity.get("content"),
                    "dense_score": float(hit.score),
                }
            )
        return items


def _dot(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) + 1e-9
    )
