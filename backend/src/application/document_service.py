import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

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
    def __init__(self, queue_runner: Any) -> None:
        self._queue_runner = queue_runner
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
                success_ids.append(document_id)

        return {"success_ids": success_ids, "failed_items": failed_items}

    async def process_build_job(self, job_id: str) -> None:
        await self._transition_running(job_id)
        await self._check_cancel(job_id)

        try:
            content = await self._parsing(job_id)
            await self._check_cancel(job_id)
            chunks = await self._chunking(job_id, content)
            await self._check_cancel(job_id)
            await self._embedding(job_id, chunks)
            await self._check_cancel(job_id)
            await self._indexing(job_id, chunks)
            await self._succeed(job_id, len(chunks))
        except AppError as exc:
            if exc.code == "DOC_JOB_STATE_CONFLICT":
                return
            await self._fail(job_id, exc.code, exc.message, detail=exc.detail)
        except Exception:
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

    async def _chunking(self, job_id: str, text: str) -> list[dict[str, Any]]:
        async with self._lock:
            job = self._jobs[job_id]
            job.stage = JobStage.chunking
            job.progress = 45
            job.message = "Chunking document"
            job.updated_at = self._now()

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            lines = [text]

        chunks = []
        for idx, line in enumerate(lines):
            keywords = [word for word in line.split(" ") if word][:5]
            chunks.append(
                {
                    "chunk_id": f"chk_{uuid4().hex[:12]}",
                    "document_id": self._jobs[job_id].document_id,
                    "chunk_index": idx,
                    "content": line,
                    "keywords": keywords,
                    "generated_questions": [f"What is the key point of chunk {idx}?"],
                    "metadata": {"length": len(line)},
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

        for chunk in chunks:
            digest = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
            if not digest:
                raise AppError("DOC_EMBEDDING_ERROR", "Document embedding failed", status_code=500)
            chunk["metadata"]["embedding_ref"] = digest[:16]

    async def _indexing(self, job_id: str, chunks: list[dict[str, Any]]) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            job.stage = JobStage.indexing
            job.progress = 90
            job.message = "Indexing chunks"
            job.updated_at = self._now()
            self._chunks[job.document_id] = chunks

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
