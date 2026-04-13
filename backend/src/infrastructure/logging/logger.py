import logging

from src.shared.request_context import document_id_ctx, job_id_ctx, request_id_ctx


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        record.job_id = job_id_ctx.get() or "-"
        record.document_id = document_id_ctx.get() or "-"
        return True


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [request_id=%(request_id)s job_id=%(job_id)s document_id=%(document_id)s] %(name)s - %(message)s",
    )
    root = logging.getLogger()
    root.addFilter(RequestIdFilter())
