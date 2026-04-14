import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.infrastructure.logging.observability import log_event
from src.shared.exceptions import AppError
from src.shared.request_context import error_code_ctx, request_id_ctx
from src.shared.schemas import ErrorResponse

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or request_id_ctx.get() or "unknown"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = _request_id(request)
        error_code_ctx.set(exc.code)
        log_event(
            logger,
            "ERROR" if exc.status_code >= 500 else "WARN",
            "http.app_error",
            route=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            error_code=exc.code,
            detail=exc.detail,
        )
        payload = ErrorResponse(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
            request_id=rid,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = _request_id(request)
        error_code_ctx.set("VALIDATION_ERROR")
        log_event(
            logger,
            "WARN",
            "http.validation_error",
            route=request.url.path,
            method=request.method,
            status_code=422,
            error_code="VALIDATION_ERROR",
            detail={"errors": exc.errors()},
        )
        payload = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            detail={"errors": exc.errors()},
            request_id=rid,
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        error_code_ctx.set("INTERNAL_ERROR")
        logger.exception(
            "http.unhandled_exception",
            extra={
                "request_id": rid,
                "route": request.url.path,
                "method": request.method,
                "status_code": 500,
                "error_code": "INTERNAL_ERROR",
            },
        )
        payload = ErrorResponse(
            code="INTERNAL_ERROR",
            message="Internal server error",
            detail=None,
            request_id=rid,
        )
        return JSONResponse(status_code=500, content=payload.model_dump())
