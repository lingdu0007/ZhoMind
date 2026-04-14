import logging

from src.infrastructure.logging.observability import ContextFieldFilter, StructuredJsonFormatter


_MANAGED_ATTR = "_zhomind_managed"


def _remove_managed_logging(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        if getattr(handler, _MANAGED_ATTR, False):
            root.removeHandler(handler)
    for filter_obj in list(root.filters):
        if getattr(filter_obj, _MANAGED_ATTR, False):
            root.removeFilter(filter_obj)


def setup_logging(level: str = "INFO", service: str = "zhomind-backend", env: str = "local") -> None:
    root = logging.getLogger()
    _remove_managed_logging(root)
    root.setLevel(level.upper())

    handler = logging.StreamHandler()
    setattr(handler, _MANAGED_ATTR, True)

    context_filter = ContextFieldFilter()
    setattr(context_filter, _MANAGED_ATTR, True)

    handler.addFilter(context_filter)
    handler.setFormatter(StructuredJsonFormatter(service=service, env=env))

    root.addFilter(context_filter)
    root.addHandler(handler)
