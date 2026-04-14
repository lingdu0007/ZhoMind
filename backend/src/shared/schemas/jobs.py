from __future__ import annotations

from pydantic import BaseModel


class JobItem(BaseModel):
    job_id: str
    document_id: str
    status: str
    stage: str
    progress: int
    message: str | None = None
    error_code: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None


class JobCancelAccepted(BaseModel):
    job_id: str
    status: str
