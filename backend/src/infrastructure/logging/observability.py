import hashlib
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Iterator, Mapping

from src.shared.request_context import (
    document_id_ctx,
    error_code_ctx,
    job_id_ctx,
    latency_ms_ctx,
    method_ctx,
    request_id_ctx,
    route_ctx,
    session_id_ctx,
    status_code_ctx,
    user_id_ctx,
)

STANDARD_FIELDS = (
    "timestamp",
    "level",
    "service",
    "env",
    "request_id",
    "user_id",
    "session_id",
    "job_id",
    "document_id",
    "route",
    "method",
    "status_code",
    "latency_ms",
    "error_code",
)

_CONTEXT_MAP: dict[str, ContextVar[Any]] = {
    "request_id": request_id_ctx,
    "user_id": user_id_ctx,
    "session_id": session_id_ctx,
    "job_id": job_id_ctx,
    "document_id": document_id_ctx,
    "route": route_ctx,
    "method": method_ctx,
    "status_code": status_code_ctx,
    "latency_ms": latency_ms_ctx,
    "error_code": error_code_ctx,
}

_SENSITIVE_KEYS = (
    "authorization",
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
)

_USER_TEXT_KEYS = {"message", "content", "prompt", "input", "query", "question", "text", "body"}
_LOG_LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARN": logging.WARNING, "ERROR": logging.ERROR}
_RESERVED_ATTRS = set(logging.makeLogRecord({}).__dict__.keys()) | {
    "message",
    "asctime",
    *STANDARD_FIELDS,
    "event",
}


def mask_secret(value: str, keep: int = 4) -> str:
    if not value:
        return "***"
    if len(value) <= keep:
        return "*" * len(value)
    return f"***{value[-keep:]}"


def _summary(text: str) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return {"length": len(text), "sha256": digest}


def redact_value(key: str, value: Any) -> Any:
    key_l = key.lower()
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(key, item) for item in value)
    if any(marker in key_l for marker in _SENSITIVE_KEYS):
        if key_l == "authorization" and isinstance(value, str):
            parts = value.split(" ", 1)
            if len(parts) == 2:
                return f"{parts[0]} {mask_secret(parts[1])}"
        return "***redacted***"
    if key_l in _USER_TEXT_KEYS and isinstance(value, str):
        return _summary(value)
    return value


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in data.items()}


def redact_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    normalized = {key.lower(): value for key, value in headers.items()}
    return redact_mapping(normalized)


def summarize_user_text(text: str) -> dict[str, Any]:
    return _summary(text)


@contextmanager
def bind_context(**fields: Any) -> Iterator[None]:
    tokens: list[tuple[ContextVar[Any], Token[Any]]] = []
    for key, value in fields.items():
        ctx = _CONTEXT_MAP.get(key)
        if ctx is None:
            continue
        tokens.append((ctx, ctx.set(value)))
    try:
        yield
    finally:
        for ctx, token in reversed(tokens):
            ctx.reset(token)


def set_context(**fields: Any) -> list[tuple[ContextVar[Any], Token[Any]]]:
    tokens: list[tuple[ContextVar[Any], Token[Any]]] = []
    for key, value in fields.items():
        ctx = _CONTEXT_MAP.get(key)
        if ctx is None:
            continue
        tokens.append((ctx, ctx.set(value)))
    return tokens


def reset_context(tokens: list[tuple[ContextVar[Any], Token[Any]]]) -> None:
    for ctx, token in reversed(tokens):
        ctx.reset(token)


def level_from_status(status_code: int) -> str:
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "WARN"
    return "INFO"


def log_event(logger: logging.Logger, level: str, event: str, **fields: Any) -> None:
    logger.log(_LOG_LEVELS[level], event, extra=redact_mapping(fields))


class ContextFieldFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or request_id_ctx.get() or "-"
        record.user_id = getattr(record, "user_id", None) or user_id_ctx.get() or "-"
        record.session_id = getattr(record, "session_id", None) or session_id_ctx.get() or "-"
        record.job_id = getattr(record, "job_id", None) or job_id_ctx.get() or "-"
        record.document_id = getattr(record, "document_id", None) or document_id_ctx.get() or "-"
        record.route = getattr(record, "route", None) or route_ctx.get() or "-"
        record.method = getattr(record, "method", None) or method_ctx.get() or "-"
        record.status_code = getattr(record, "status_code", None)
        if record.status_code is None:
            record.status_code = status_code_ctx.get()
        record.latency_ms = getattr(record, "latency_ms", None)
        if record.latency_ms is None:
            record.latency_ms = latency_ms_ctx.get()
        record.error_code = getattr(record, "error_code", None) or error_code_ctx.get() or "-"
        return True


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, service: str, env: str) -> None:
        super().__init__()
        self._service = service
        self._env = env

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value in ("", "-", None):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in ("", "-", None):
            return None
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self._service,
            "env": self._env,
            "request_id": getattr(record, "request_id", "-") or "-",
            "user_id": getattr(record, "user_id", "-") or "-",
            "session_id": getattr(record, "session_id", "-") or "-",
            "job_id": getattr(record, "job_id", "-") or "-",
            "document_id": getattr(record, "document_id", "-") or "-",
            "route": getattr(record, "route", "-") or "-",
            "method": getattr(record, "method", "-") or "-",
            "status_code": self._to_int(getattr(record, "status_code", None)),
            "latency_ms": self._to_float(getattr(record, "latency_ms", None)),
            "error_code": getattr(record, "error_code", "-") or "-",
            "event": record.getMessage(),
            "logger": record.name,
        }

        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_ATTRS and not key.startswith("_")
        }
        if extra_fields:
            payload["details"] = redact_mapping(extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, default=str)
