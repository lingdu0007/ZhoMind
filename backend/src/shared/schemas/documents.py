from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentItem(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_strategy: str
    chunk_count: int | None
    uploaded_at: str | None
    ready_at: str | None


class DocumentUploadAccepted(BaseModel):
    job_id: str
    document_id: str
    status: str
    message: str


class DocumentBuildRequest(BaseModel):
    chunk_strategy: str


class DocumentBatchBuildRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    chunk_strategy: str


class DocumentBatchDeleteRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
