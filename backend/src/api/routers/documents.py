from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status

from src.api.dependencies import require_admin
from src.application.document_service import CHUNK_STRATEGIES
from src.shared.exceptions import AppError
from src.shared.schemas import ListResponse, PaginationMeta
from src.shared.schemas.documents import (
    DocumentBatchBuildRequest,
    DocumentBatchDeleteRequest,
    DocumentBuildRequest,
    DocumentUploadAccepted,
)

router = APIRouter(prefix="/documents", tags=["documents"])
DOCUMENT_STATUSES = {"pending", "processing", "ready", "failed", "deleting"}


def _paginate(items: list[dict], page: int, page_size: int) -> ListResponse:
    start = (page - 1) * page_size
    end = start + page_size
    return ListResponse(
        items=items[start:end],
        pagination=PaginationMeta(page=page, page_size=page_size, total=len(items)),
    )


@router.get("", response_model=ListResponse)
async def list_documents(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    status: str | None = Query(default=None),
    subject: dict = Depends(require_admin),
) -> ListResponse:
    _ = keyword, sort
    if status and status not in DOCUMENT_STATUSES:
        raise AppError("VALIDATION_ERROR", "Invalid status", detail={"status": status}, status_code=422)

    service = request.app.state.document_service
    items = await service.list_documents(status=status)
    return _paginate(items, page=page, page_size=page_size)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadAccepted)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    subject: dict = Depends(require_admin),
) -> dict:
    service = request.app.state.document_service
    content = await file.read()
    return await service.create_upload_job(
        filename=file.filename or "unknown",
        file_type=file.content_type or "application/octet-stream",
        content=content,
    )


@router.post("/{document_id}/build", status_code=status.HTTP_202_ACCEPTED)
async def build_document(
    document_id: str,
    payload: DocumentBuildRequest,
    request: Request,
    subject: dict = Depends(require_admin),
) -> dict:
    service = request.app.state.document_service
    return await service.create_build_job(document_id=document_id, chunk_strategy=payload.chunk_strategy)


@router.post("/batch-build", status_code=status.HTTP_202_ACCEPTED)
async def batch_build(
    payload: DocumentBatchBuildRequest,
    request: Request,
    subject: dict = Depends(require_admin),
) -> dict:
    if payload.chunk_strategy not in CHUNK_STRATEGIES:
        raise AppError("DOC_INVALID_CHUNK_STRATEGY", "Invalid chunk strategy", status_code=422)

    service = request.app.state.document_service
    items: list[dict] = []
    failed_items: list[dict] = []
    for document_id in payload.document_ids:
        try:
            item = await service.create_build_job(document_id=document_id, chunk_strategy=payload.chunk_strategy)
            items.append(
                {
                    "document_id": item["document_id"],
                    "job_id": item["job_id"],
                    "status": item["status"],
                }
            )
        except AppError as exc:
            failed_items.append(
                {
                    "document_id": document_id,
                    "error_code": exc.code,
                    "message": exc.message,
                    "detail": exc.detail,
                }
            )
    return {"items": items, "failed_items": failed_items}


@router.post("/batch-delete")
async def batch_delete(
    payload: DocumentBatchDeleteRequest,
    request: Request,
    subject: dict = Depends(require_admin),
) -> dict:
    service = request.app.state.document_service
    return await service.batch_delete(payload.document_ids)


@router.get("/{document_id}/chunks", response_model=ListResponse)
async def list_document_chunks(
    document_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    subject: dict = Depends(require_admin),
) -> ListResponse:
    service = request.app.state.document_service
    items = await service.list_chunks(document_id)
    return _paginate(items, page=page, page_size=page_size)


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_by_filename(
    filename: str,
    request: Request,
    subject: dict = Depends(require_admin),
) -> None:
    service = request.app.state.document_service
    docs = await service.list_documents(status=None)
    target = next((doc for doc in docs if doc["filename"] == filename), None)
    if not target:
        raise AppError("RESOURCE_NOT_FOUND", "Document not found", status_code=404)

    result = await service.batch_delete([target["document_id"]])
    if result["failed_items"]:
        failed = result["failed_items"][0]
        raise AppError(failed.get("code", "RESOURCE_CONFLICT"), failed.get("message", "Delete failed"), status_code=409)
    return None
