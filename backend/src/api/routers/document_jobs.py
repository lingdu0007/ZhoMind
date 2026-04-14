import json
import logging

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from src.api.dependencies import require_admin
from src.infrastructure.logging.observability import log_event
from src.shared.exceptions import AppError
from src.shared.schemas import ListResponse, PaginationMeta
from src.shared.schemas.jobs import JobCancelAccepted, JobItem

router = APIRouter(prefix="/documents/jobs", tags=["documents"])
logger = logging.getLogger(__name__)

JOB_STATUSES = {"queued", "running", "succeeded", "failed", "canceled"}


JOB_PUBLIC_FIELDS = (
    "job_id",
    "document_id",
    "status",
    "stage",
    "progress",
    "message",
    "error_code",
    "created_at",
    "updated_at",
    "finished_at",
)


def _normalize_job(job: dict) -> dict:
    return {key: job.get(key) for key in JOB_PUBLIC_FIELDS}


def _paginate(items: list[dict], page: int, page_size: int) -> ListResponse:
    start = (page - 1) * page_size
    end = start + page_size
    return ListResponse(
        items=items[start:end],
        pagination=PaginationMeta(page=page, page_size=page_size, total=len(items)),
    )


@router.get("", response_model=ListResponse)
async def list_jobs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    subject: dict = Depends(require_admin),
) -> ListResponse:
    if status and status not in JOB_STATUSES:
        raise AppError("VALIDATION_ERROR", "Invalid status", detail={"status": status}, status_code=422)

    service = request.app.state.document_service
    items = await service.list_jobs(status=status, document_id=document_id)
    normalized = [_normalize_job(item) for item in items]
    log_event(
        logger,
        "INFO",
        "documents.jobs.list.succeeded",
        status_filter=status,
        document_id=document_id,
        total=len(normalized),
    )
    return _paginate(normalized, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobItem)
async def get_job(job_id: str, request: Request, subject: dict = Depends(require_admin)) -> dict:
    service = request.app.state.document_service
    job = await service.get_job(job_id)
    log_event(
        logger,
        "INFO",
        "documents.jobs.get.succeeded",
        job_id=job_id,
        document_id=job.get("document_id"),
        status=job.get("status"),
        stage=job.get("stage"),
    )
    return _normalize_job(job)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, request: Request, subject: dict = Depends(require_admin)) -> StreamingResponse:
    service = request.app.state.document_service
    job = _normalize_job(await service.get_job(job_id))
    request_id = getattr(request.state, "request_id", "")
    log_event(
        logger,
        "INFO",
        "documents.jobs.stream.started",
        request_id=request_id,
        job_id=job_id,
        document_id=job.get("document_id"),
        status=job.get("status"),
    )

    async def _event_stream():
        progress_data = {
            "job_id": job["job_id"],
            "status": job["status"],
            "stage": job["stage"],
            "progress": job["progress"],
            "message": job.get("message"),
            "error_code": job.get("error_code"),
        }
        yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
        log_event(
            logger,
            "INFO",
            "documents.jobs.stream.first_packet",
            request_id=request_id,
            job_id=job_id,
            document_id=job.get("document_id"),
            status=job.get("status"),
            stage=job.get("stage"),
        )

        if job["status"] == "failed":
            error_data = {
                "job_id": job["job_id"],
                "status": job["status"],
                "stage": job["stage"],
                "progress": job["progress"],
                "message": job.get("message"),
                "error_code": job.get("error_code"),
                "detail": job.get("detail"),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
            log_event(
                logger,
                "WARN",
                "documents.jobs.stream.error_packet",
                request_id=request_id,
                job_id=job_id,
                document_id=job.get("document_id"),
                error_code=job.get("error_code") or "-",
            )

        done_data = {
            "job_id": job["job_id"],
            "status": job["status"],
            "stage": job["stage"],
            "progress": job["progress"],
            "message": job.get("message"),
            "error_code": job.get("error_code"),
            "detail": job.get("detail"),
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
        log_event(
            logger,
            "INFO",
            "documents.jobs.stream.completed",
            request_id=request_id,
            job_id=job_id,
            document_id=job.get("document_id"),
            status=job.get("status"),
        )

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED, response_model=JobCancelAccepted)
async def cancel_job(job_id: str, request: Request, subject: dict = Depends(require_admin)) -> dict:
    service = request.app.state.document_service
    result = await service.cancel_job(job_id)
    log_event(logger, "INFO", "documents.jobs.cancel.accepted", job_id=job_id, status=result.get("status"))
    return result
