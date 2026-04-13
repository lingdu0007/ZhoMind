from fastapi import APIRouter

from src.shared.exceptions import NotImplementedErrorApp
from src.shared.schemas import ListResponse, PaginationMeta

router = APIRouter(prefix="/document_jobs", tags=["document_jobs"])


@router.get("", response_model=ListResponse)
async def list_jobs() -> ListResponse:
    return ListResponse(items=[], pagination=PaginationMeta())


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "uploaded",
        "progress": 0,
    }


@router.get("/{job_id}/stream")
async def stream_job(job_id: str) -> dict:
    _ = job_id
    raise NotImplementedErrorApp()


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "status": "canceled",
    }
