from pathlib import Path

from pydantic import BaseModel, Field

__path__ = [str(Path(__file__).with_suffix(""))]


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: dict | None = None
    request_id: str


class PaginationMeta(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    total: int = Field(default=0, ge=0)


class ListResponse(BaseModel):
    items: list
    pagination: PaginationMeta
