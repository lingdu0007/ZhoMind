import logging

from src.shared.request_context import request_id_ctx


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s - %(message)s",
    )
    root = logging.getLogger()
    root.addFilter(RequestIdFilter())
