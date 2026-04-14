import logging

from src.infrastructure.logging.observability import ContextFieldFilter, StructuredJsonFormatter


def setup_logging(level: str = "INFO", service: str = "zhomind-backend", env: str = "local") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()
    root.setLevel(level.upper())

    handler = logging.StreamHandler()
    context_filter = ContextFieldFilter()
    handler.addFilter(context_filter)
    handler.setFormatter(StructuredJsonFormatter(service=service, env=env))

    root.addFilter(context_filter)
    root.addHandler(handler)
