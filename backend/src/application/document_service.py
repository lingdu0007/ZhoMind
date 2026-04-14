import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.infrastructure.logging.observability import log_event
from src.infrastructure.retrieval.tuning import RetrievalTuning
from src.shared.exceptions import AppError
from src.shared.request_context import document_id_ctx, job_id_ctx


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class JobStage(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    chunking = "chunking"
    embedding = "embedding"
    indexing = "indexing"
    completed = "completed"
    failed = "failed"

logger = logging.getLogger(__name__)

CHUNK_STRATEGIES = {"padding", "general", "book", "paper", "resume", "table", "qa"}


@dataclass
class DocumentRecord:
    document_id: str
    filename: str
    file_type: str
    file_size: int
    content: bytes
    status: str = "pending"
    chunk_strategy: str = "general"
    chunk_count: int | None = None
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ready_at: datetime | None = None


@dataclass
class JobRecord:
    job_id: str
    document_id: str
    status: JobStatus
    stage: JobStage
    progress: int
    message: str | None
    error_code: str | None
    detail: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    cancel_requested: bool = False
    attempt: int = 0


class DocumentService:
    def __init__(
        self,
        queue_runner: Any,
        vector_store: Any | None = None,
        bm25_store: Any | None = None,
        index_sync_service: Any | None = None,
        tuning: RetrievalTuning | None = None,
    ) -> None:
        self._queue_runner = queue_runner
        self._vector_store = vector_store
        self._bm25_store = bm25_store
        self._index_sync_service = index_sync_service
        self._tuning = tuning or RetrievalTuning(
            dense_weight=0.55,
            sparse_weight=0.45,
            bm25_min_term_match=1,
            bm25_min_score=0.05,
            dense_top_k=30,
            sparse_top_k=30,
            dense_rescue_enabled=True,
            max_document_filter_count=20,
            max_context_tokens=5000,
            chunk_version_retention=2,
            max_chunk_count_per_document=2000,
            max_bm25_postings_per_document=50000,
        )
        self._documents: dict[str, DocumentRecord] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._chunks: dict[str, list[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat().replace("+00:00", "Z") if value else None

    def _job_to_dict(self, job: JobRecord) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "document_id": job.document_id,
            "status": job.status.value,
            "stage": job.stage.value,
            "progress": job.progress,
            "message": job.message,
            "error_code": job.error_code,
            "detail": job.detail,
            "created_at": self._iso(job.created_at),
            "updated_at": self._iso(job.updated_at),
            "finished_at": self._iso(job.finished_at),
        }

    def _doc_to_dict(self, doc: DocumentRecord) -> dict[str, Any]:
        return {
            "document_id": doc.document_id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "status": doc.status,
            "chunk_strategy": doc.chunk_strategy,
            "chunk_count": doc.chunk_count,
            "uploaded_at": self._iso(doc.uploaded_at),
            "ready_at": self._iso(doc.ready_at),
        }

    async def create_upload_job(self, filename: str, file_type: str, content: bytes) -> dict[str, Any]:
        document_id = f"doc_{uuid4().hex[:12]}"
        job_id = f"job_{uuid4().hex[:12]}"
        now = self._now()

        async with self._lock:
            self._documents[document_id] = DocumentRecord(
                document_id=document_id,
                filename=filename,
                file_type=file_type,
                file_size=len(content),
                content=content,
            )
            self._jobs[job_id] = JobRecord(
                job_id=job_id,
                document_id=document_id,
                status=JobStatus.queued,
                stage=JobStage.uploaded,
                progress=0,
                message="Document accepted for async indexing",
                error_code=None,
                detail=None,
                created_at=now,
                updated_at=now,
                finished_at=None,
            )

        await self._queue_runner.enqueue("document.build", {"job_id": job_id})
        return {
            "job_id": job_id,
            "document_id": document_id,
            "status": JobStatus.queued.value,
            "message": "Document accepted for async indexing",
        }

    async def create_build_job(self, document_id: str, chunk_strategy: str) -> dict[str, Any]:
        if chunk_strategy not in CHUNK_STRATEGIES:
            raise AppError("DOC_INVALID_CHUNK_STRATEGY", "Invalid chunk strategy", status_code=422)

        async with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                raise AppError("RESOURCE_NOT_FOUND", "Document not found", status_code=404)
            doc.chunk_strategy = chunk_strategy
            doc.status = "pending"
            doc.ready_at = None

            job_id = f"job_{uuid4().hex[:12]}"
            now = self._now()
            self._jobs[job_id] = JobRecord(
                job_id=job_id,
                document_id=document_id,
                status=JobStatus.queued,
                stage=JobStage.uploaded,
                progress=0,
                message="Document accepted for async indexing",
                error_code=None,
                detail=None,
                created_at=now,
                updated_at=now,
                finished_at=None,
            )

        await self._queue_runner.enqueue("document.build", {"job_id": job_id})
        return {
            "job_id": job_id,
            "document_id": document_id,
            "status": JobStatus.queued.value,
            "message": "Document accepted for async indexing",
        }

    async def list_documents(self, status: str | None = None) -> list[dict[str, Any]]:
        async with self._lock:
            items = [self._doc_to_dict(doc) for doc in self._documents.values()]
        if status:
            items = [item for item in items if item["status"] == status]
        return sorted(items, key=lambda item: item["uploaded_at"], reverse=True)

    async def list_jobs(self, status: str | None = None, document_id: str | None = None) -> list[dict[str, Any]]:
        async with self._lock:
            items = [self._job_to_dict(job) for job in self._jobs.values()]
        if status:
            items = [item for item in items if item["status"] == status]
        if document_id:
            items = [item for item in items if item["document_id"] == document_id]
        return sorted(items, key=lambda item: item["created_at"], reverse=True)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise AppError("DOC_JOB_NOT_FOUND", "Job not found", status_code=404)
            return self._job_to_dict(job)

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise AppError("DOC_JOB_NOT_FOUND", "Job not found", status_code=404)
            if job.status not in {JobStatus.queued, JobStatus.running}:
                raise AppError("DOC_JOB_STATE_CONFLICT", "Job already finished", status_code=409)

            job.cancel_requested = True
            if job.status == JobStatus.queued:
                now = self._now()
                job.status = JobStatus.canceled
                job.stage = JobStage.failed
                job.progress = max(job.progress, 1)
                job.message = "Job canceled"
                job.error_code = None
                job.detail = {"reason": "canceled"}
                job.updated_at = now
                job.finished_at = now
                doc = self._documents.get(job.document_id)
                if doc:
                    doc.status = "failed"
            return {"job_id": job_id, "status": JobStatus.canceled.value}

    async def list_chunks(self, document_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                raise AppError("RESOURCE_NOT_FOUND", "Document not found", status_code=404)
            if doc.status != "ready":
                raise AppError("DOC_CHUNK_RESULT_NOT_READY", "Chunk result not ready", status_code=409)
            return list(self._chunks.get(document_id, []))

    async def hybrid_retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        dense_rows = self._vector_store.query(query, top_k=self._tuning.dense_top_k) if self._vector_store else []
        sparse_rows = self._bm25_store.query(query, top_k=self._tuning.sparse_top_k) if self._bm25_store else []

        merged: dict[str, dict[str, Any]] = {}
        for row in dense_rows:
            merged[row["chunk_id"]] = {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "content": row.get("content", ""),
                "dense_score": float(row.get("dense_score", 0.0)),
                "sparse_score": 0.0,
            }
        for row in sparse_rows:
            current = merged.get(row["chunk_id"])
            if current is None:
                current = {
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "content": row.get("content", ""),
                    "dense_score": 0.0,
                    "sparse_score": 0.0,
                }
                merged[row["chunk_id"]] = current
            current["sparse_score"] = float(row.get("sparse_score", 0.0))

        fused = []
        for item in merged.values():
            dense_score = max(0.0, min(1.0, item["dense_score"]))
            sparse_score = max(0.0, min(1.0, item["sparse_score"]))
            fused_score = (
                dense_score * self._tuning.dense_weight
                + sparse_score * self._tuning.sparse_weight
            )
            if self._tuning.dense_rescue_enabled and sparse_score >= self._tuning.bm25_min_score:
                fused_score = max(fused_score, sparse_score * self._tuning.sparse_weight)
            fused.append({**item, "score": round(fused_score, 6)})

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:top_k]

    async def batch_delete(self, document_ids: list[str]) -> dict[str, Any]:
        success_ids: list[str] = []
        failed_items: list[dict[str, str]] = []
        for document_id in document_ids:
            async with self._lock:
                doc = self._documents.get(document_id)
                if not doc:
                    failed_items.append(
                        {"document_id": document_id, "code": "RESOURCE_NOT_FOUND", "message": "Document not found"}
                    )
                    continue

                running_jobs = [
                    job
                    for job in self._jobs.values()
                    if job.document_id == document_id and job.status in {JobStatus.queued, JobStatus.running}
                ]
                for job in running_jobs:
                    job.cancel_requested = True
                doc.status = "deleting"
                self._documents.pop(document_id, None)
                self._chunks.pop(document_id, None)
                if self._index_sync_service is not None:
                    await self._index_sync_service.delete_document_index(document_id=document_id)
                success_ids.append(document_id)

        return {"success_ids": success_ids, "failed_items": failed_items}

    async def process_build_job(self, job_id: str) -> None:
        await self._transition_running(job_id)
        await self._check_cancel(job_id)

        try:
            log_event(logger, "INFO", "doc.pipeline.parsing.started", job_id=job_id)
            content = await self._parsing(job_id)
            log_event(logger, "INFO", "doc.pipeline.parsing.completed", job_id=job_id)
            await self._check_cancel(job_id)

            log_event(logger, "INFO", "doc.pipeline.chunking.started", job_id=job_id)
            chunks = await self._chunking(job_id, content)
            log_event(logger, "INFO", "doc.pipeline.chunking.completed", job_id=job_id, chunk_count=len(chunks))
            await self._check_cancel(job_id)

            log_event(logger, "INFO", "doc.pipeline.embedding.started", job_id=job_id)
            await self._embedding(job_id, chunks)
            log_event(logger, "INFO", "doc.pipeline.embedding.completed", job_id=job_id)
            await self._check_cancel(job_id)

            log_event(logger, "INFO", "doc.pipeline.indexing.started", job_id=job_id)
            await self._indexing(job_id, chunks)
            log_event(logger, "INFO", "doc.pipeline.indexing.completed", job_id=job_id)
            await self._succeed(job_id, len(chunks))
        except AppError as exc:
            if exc.code == "DOC_JOB_STATE_CONFLICT":
                return
            log_event(logger, "ERROR", "doc.pipeline.failed", job_id=job_id, error_code=exc.code)
            await self._fail(job_id, exc.code, exc.message, detail=exc.detail)
        except Exception:
            log_event(logger, "ERROR", "doc.pipeline.failed", job_id=job_id, error_code="INTERNAL_ERROR")
            await self._fail(job_id, "INTERNAL_ERROR", "Internal pipeline error", detail=None)

    async def _transition_running(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise AppError("DOC_JOB_NOT_FOUND", "Job not found", status_code=404)
            if job.status == JobStatus.canceled:
                raise AppError("DOC_JOB_STATE_CONFLICT", "Job canceled", status_code=409)
            job.status = JobStatus.running
            job.stage = JobStage.parsing
            job.progress = 10
            job.message = "Parsing document"
            job.error_code = None
            job.detail = None
            job.updated_at = self._now()
            doc = self._documents.get(job.document_id)
            if doc:
                doc.status = "processing"

        logger.info(
            "job_stage_transition",
            extra={"job_id": job.job_id, "document_id": job.document_id, "stage": job.stage.value},
        )

    async def _check_cancel(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise AppError("DOC_JOB_NOT_FOUND", "Job not found", status_code=404)
            if not job.cancel_requested:
                return
            now = self._now()
            job.status = JobStatus.canceled
            job.stage = JobStage.failed
            job.message = "Job canceled"
            job.error_code = None
            job.detail = {"reason": "canceled"}
            job.updated_at = now
            job.finished_at = now
            doc = self._documents.get(job.document_id)
            if doc:
                doc.status = "failed"
        raise AppError("DOC_JOB_STATE_CONFLICT", "Job canceled", status_code=409)

    async def _parsing(self, job_id: str) -> str:
        async with self._lock:
            job = self._jobs[job_id]
            doc = self._documents.get(job.document_id)
            if not doc:
                raise AppError("RESOURCE_NOT_FOUND", "Document not found", status_code=404)
            job.stage = JobStage.parsing
            job.progress = 25
            job.message = "Parsing document"
            job.updated_at = self._now()
            text = doc.content.decode("utf-8", errors="ignore").strip()
            if not text:
                raise AppError("DOC_PARSE_ERROR", "Document parse failed", status_code=500)
            return text

    def _chunk_params(self, strategy: str) -> tuple[int, int]:
        mapping = {
            "padding": (180, 40),
            "general": (320, 60),
            "book": (500, 80),
            "paper": (420, 70),
            "resume": (220, 40),
            "table": (260, 30),
            "qa": (180, 20),
        }
        return mapping.get(strategy, (320, 60))

    def _split_with_overlap(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        clean = " ".join(text.split())
        if not clean:
            return []
        if len(clean) <= chunk_size:
            return [clean]

        result: list[str] = []
        start = 0
        step = max(1, chunk_size - overlap)
        while start < len(clean):
            end = min(len(clean), start + chunk_size)
            result.append(clean[start:end])
            if end >= len(clean):
                break
            start += step
        return result

    async def _chunking(self, job_id: str, text: str) -> list[dict[str, Any]]:
        async with self._lock:
            job = self._jobs[job_id]
            doc = self._documents.get(job.document_id)
            if not doc:
                raise AppError("RESOURCE_NOT_FOUND", "Document not found", status_code=404)
            job.stage = JobStage.chunking
            job.progress = 45
            job.message = "Chunking document"
            job.updated_at = self._now()
            strategy = doc.chunk_strategy

        chunk_size, overlap = self._chunk_params(strategy)
        segments = self._split_with_overlap(text, chunk_size, overlap)
        if not segments:
            segments = [text]

        chunks = []
        for idx, line in enumerate(segments):
            keywords = [word for word in line.split(" ") if word][:5]
            chunks.append(
                {
                    "chunk_id": f"chk_{uuid4().hex[:12]}",
                    "document_id": self._jobs[job_id].document_id,
                    "chunk_index": idx,
                    "content": line,
                    "keywords": keywords,
                    "generated_questions": [f"What is the key point of chunk {idx}?"],
                    "metadata": {"length": len(line), "chunk_strategy": strategy},
                }
            )
        return chunks

    async def _embedding(self, job_id: str, chunks: list[dict[str, Any]]) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            job.stage = JobStage.embedding
            job.progress = 70
            job.message = "Embedding chunks"
            job.updated_at = self._now()

        try:
            for chunk in chunks:
                digest = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
                if not digest:
                    raise AppError("DOC_EMBEDDING_ERROR", "Document embedding failed", status_code=500)
                chunk["metadata"]["embedding_ref"] = digest[:16]
            if self._vector_store is not None:
                self._vector_store.upsert(chunks)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "DOC_EMBEDDING_ERROR",
                "Document embedding failed",
                detail={"reason": str(exc)},
                status_code=500,
            ) from exc

    async def _indexing(self, job_id: str, chunks: list[dict[str, Any]]) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            job.stage = JobStage.indexing
            job.progress = 90
            job.message = "Indexing chunks"
            job.updated_at = self._now()
            self._chunks[job.document_id] = chunks

        try:
            if self._bm25_store is not None:
                self._bm25_store.upsert(chunks)
        except Exception as exc:
            raise AppError(
                "RAG_UPSTREAM_ERROR",
                "RAG upstream error",
                detail={"reason": str(exc)},
                status_code=500,
            ) from exc

        if self._index_sync_service is not None:
            try:
                await self._index_sync_service.replace_and_rebuild_document_chunks(
                    document_id=job.document_id,
                    chunks=chunks,
                    version=1,
                )
            except Exception as exc:
                log_event(
                    logger,
                    "WARN",
                    "doc.pipeline.index_sync.degraded",
                    job_id=job.job_id,
                    document_id=job.document_id,
                    error_code="RETRIEVAL_SYNC_DEGRADED",
                    detail={"reason": str(exc)},
                )

    async def _succeed(self, job_id: str, chunk_count: int) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            now = self._now()
            job.status = JobStatus.succeeded
            job.stage = JobStage.completed
            job.progress = 100
            job.message = "Document indexed"
            job.error_code = None
            job.detail = None
            job.updated_at = now
            job.finished_at = now

            doc = self._documents.get(job.document_id)
            if doc:
                doc.status = "ready"
                doc.chunk_count = chunk_count
                doc.ready_at = now

        logger.info(
            "job_succeeded",
            extra={"job_id": job.job_id, "document_id": job.document_id},
        )

    async def _fail(
        self,
        job_id: str,
        error_code: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            now = self._now()
            job.status = JobStatus.failed
            job.stage = JobStage.failed
            job.progress = min(job.progress, 99)
            job.message = message
            job.error_code = error_code
            job.detail = detail
            job.updated_at = now
            job.finished_at = now
            doc = self._documents.get(job.document_id)
            if doc:
                doc.status = "failed"

        logger.error(
            "job_failed",
            extra={"job_id": job.job_id, "document_id": job.document_id, "error_code": error_code},
        )


class DocumentTaskExecutor:
    def __init__(self, service: DocumentService) -> None:
        self._service = service

    async def execute(self, task_name: str, payload: dict) -> None:
        if task_name != "document.build":
            return

        job_id = payload.get("job_id")
        if not job_id:
            return

        token_job = job_id_ctx.set(job_id)
        try:
            job = await self._service.get_job(job_id)
            token_doc = document_id_ctx.set(job["document_id"])
            try:
                await self._service.process_build_job(job_id)
            finally:
                document_id_ctx.reset(token_doc)
        finally:
            job_id_ctx.reset(token_job)
