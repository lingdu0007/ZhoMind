from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")
session_id_ctx: ContextVar[str] = ContextVar("session_id", default="")
job_id_ctx: ContextVar[str] = ContextVar("job_id", default="")
document_id_ctx: ContextVar[str] = ContextVar("document_id", default="")
route_ctx: ContextVar[str] = ContextVar("route", default="")
method_ctx: ContextVar[str] = ContextVar("method", default="")
status_code_ctx: ContextVar[int | None] = ContextVar("status_code", default=None)
latency_ms_ctx: ContextVar[float | None] = ContextVar("latency_ms", default=None)
error_code_ctx: ContextVar[str] = ContextVar("error_code", default="")
