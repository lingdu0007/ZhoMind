import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.infrastructure.logging.observability import level_from_status, log_event, redact_headers, reset_context, set_context
from src.shared.request_context import error_code_ctx

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", f"req_{uuid.uuid4().hex[:12]}")
        tokens = set_context(
            request_id=request_id,
            user_id="",
            session_id="",
            job_id="",
            document_id="",
            route=request.url.path,
            method=request.method,
            status_code=None,
            latency_ms=None,
            error_code="",
        )
        request.state.request_id = request_id
        started = time.perf_counter()

        log_event(
            logger,
            "INFO",
            "http.request.start",
            route=request.url.path,
            method=request.method,
            headers=redact_headers(dict(request.headers)),
        )
        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - started) * 1000
            response.headers["x-request-id"] = request_id
            level = level_from_status(response.status_code)
            log_event(
                logger,
                level,
                "http.request.complete",
                route=request.url.path,
                method=request.method,
                status_code=response.status_code,
                latency_ms=latency_ms,
                error_code=error_code_ctx.get() or "-",
            )
            return response
        except Exception:
            latency_ms = (time.perf_counter() - started) * 1000
            log_event(
                logger,
                "ERROR",
                "http.request.exception",
                route=request.url.path,
                method=request.method,
                status_code=500,
                latency_ms=latency_ms,
                error_code=error_code_ctx.get() or "INTERNAL_ERROR",
            )
            raise
        finally:
            reset_context(tokens)
