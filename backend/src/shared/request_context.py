from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
job_id_ctx: ContextVar[str] = ContextVar("job_id", default="")
document_id_ctx: ContextVar[str] = ContextVar("document_id", default="")
