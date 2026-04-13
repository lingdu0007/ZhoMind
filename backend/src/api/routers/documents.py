from fastapi import APIRouter

from src.shared.schemas import ListResponse, PaginationMeta

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=ListResponse)
async def list_documents() -> ListResponse:
    return ListResponse(items=[], pagination=PaginationMeta())


@router.post("/upload")
async def upload_document() -> dict:
    return {
        "code": "NOT_IMPLEMENTED",
        "message": "Endpoint not implemented",
        "detail": None,
    }


@router.post("/{document_id}/build")
async def build_document(document_id: str) -> dict:
    return {
        "code": "NOT_IMPLEMENTED",
        "message": "Endpoint not implemented",
        "detail": {"document_id": document_id},
    }


@router.post("/batch-build")
async def batch_build() -> ListResponse:
    return ListResponse(items=[], pagination=PaginationMeta(page=1, page_size=20, total=0))


@router.post("/batch-delete")
async def batch_delete() -> dict:
    return {"success_ids": [], "failed_items": []}


@router.get("/{document_id}/chunks", response_model=ListResponse)
async def list_document_chunks(document_id: str) -> ListResponse:
    _ = document_id
    return ListResponse(items=[], pagination=PaginationMeta())
