import io
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infrastructure.config.settings import get_settings
from src.infrastructure.logging.observability import (
    ContextFieldFilter,
    STANDARD_FIELDS,
    StructuredJsonFormatter,
    bind_context,
    log_event,
    summarize_user_text,
)


def _parse_json_lines(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return rows


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _contains_event(logs: list[dict[str, Any]], event_name: str) -> bool:
    return any(item.get("event") == event_name for item in logs)


def main() -> None:
    settings = get_settings()
    stream = io.StringIO()
    logger = logging.getLogger("observability.selfcheck")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFieldFilter())
    handler.setFormatter(StructuredJsonFormatter(service=settings.app_name, env=settings.env))
    logger.addHandler(handler)

    with bind_context(
        request_id="req_obs_20260414_001",
        user_id="user_001",
        session_id="ses_001",
        route="/api/v1/chat",
        method="POST",
    ):
        log_event(
            logger,
            "INFO",
            "chat.request.started",
            input_summary=summarize_user_text("sensitive prompt should not be stored in plain text"),
        )
        log_event(
            logger,
            "WARN",
            "auth.login.failed",
            error_code="AUTH_BAD_CREDENTIALS",
            headers={"authorization": "Bearer user-secret-token"},
        )
        log_event(
            logger,
            "INFO",
            "http.request.complete",
            status_code=401,
            latency_ms=18.6,
            error_code="AUTH_BAD_CREDENTIALS",
        )

    with bind_context(
        request_id="req_obs_20260414_002",
        job_id="job_001",
        document_id="doc_001",
        route="worker:document.build",
        method="QUEUE",
    ):
        log_event(logger, "INFO", "documents.job.stage_transition", stage="embedding", progress=70)
        log_event(logger, "INFO", "documents.job.succeeded", status="succeeded", stage="completed", progress=100)

    logs = _parse_json_lines(stream.getvalue())
    _assert(logs, "no structured logs captured")

    for item in logs:
        for field in STANDARD_FIELDS:
            _assert(field in item, f"missing required field: {field}")

    _assert(_contains_event(logs, "chat.request.started"), "missing event: chat.request.started")
    _assert(_contains_event(logs, "auth.login.failed"), "missing event: auth.login.failed")
    _assert(_contains_event(logs, "http.request.complete"), "missing event: http.request.complete")
    _assert(_contains_event(logs, "documents.job.succeeded"), "missing event: documents.job.succeeded")

    failed_login = next(item for item in logs if item.get("event") == "auth.login.failed")
    auth_value = failed_login.get("details", {}).get("headers", {}).get("authorization", "")
    _assert("user-secret-token" not in auth_value, "authorization token must be masked")
    _assert(auth_value.startswith("Bearer "), "authorization mask must preserve scheme")
    _assert(failed_login.get("error_code") == "AUTH_BAD_CREDENTIALS", "error_code must be set")

    chat_start = next(item for item in logs if item.get("event") == "chat.request.started")
    summary = chat_start.get("details", {}).get("input_summary", {})
    _assert("sha256" in summary and "length" in summary, "chat input must use summary only")

    sample = next(item for item in logs if item.get("event") == "documents.job.succeeded")
    print(f"SELF_CHECK_OK logs={len(logs)}")
    print(f"SAMPLE_LOG {json.dumps(sample, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
