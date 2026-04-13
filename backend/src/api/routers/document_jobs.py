import json

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_current_subject
from src.shared.exceptions import AppError
from src.shared.schemas import ListResponse, PaginationMeta

router = APIRouter(prefix="/documents/jobs", tags=["documents"])

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


def _require_admin(subject: dict) -> None:
    if subject.get("role") != "admin":
        raise AppError("AUTH_FORBIDDEN", "Forbidden", status_code=403)


@router.get("", response_model=ListResponse)
async def list_jobs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    subject: dict = Depends(get_current_subject),
) -> ListResponse:
    _require_admin(subject)
    if status and status not in JOB_STATUSES:
        raise AppError("VALIDATION_ERROR", "Invalid status", detail={"status": status}, status_code=422)

    service = request.app.state.document_service
    items = await service.list_jobs(status=status, document_id=document_id)
    normalized = [_normalize_job(item) for item in items]
    return _paginate(normalized, page=page, page_size=page_size)


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request, subject: dict = Depends(get_current_subject)) -> dict:
    _require_admin(subject)
    service = request.app.state.document_service
    job = await service.get_job(job_id)
    return _normalize_job(job)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, request: Request, subject: dict = Depends(get_current_subject)) -> StreamingResponse:
    _require_admin(subject)
    service = request.app.state.document_service
    job = _normalize_job(await service.get_job(job_id))

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

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_job(job_id: str, request: Request, subject: dict = Depends(get_current_subject)) -> dict:
    _require_admin(subject)
    service = request.app.state.document_service
    return await service.cancel_job(job_id)
