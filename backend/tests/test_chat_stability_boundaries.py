import asyncio

from fastapi.testclient import TestClient

from src.main import app


def test_chat_empty_input_validation() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 422
        payload = resp.json()
        assert payload["code"] == "VALIDATION_ERROR"
        assert payload["message"] == "Request validation failed"


def test_chat_long_text_still_returns_contract_shape() -> None:
    with TestClient(app) as client:
        text = "长文本" * 2000
        resp = client.post("/api/v1/chat", json={"message": text})
        assert resp.status_code == 200
        payload = resp.json()
        assert "session_id" in payload
        assert payload["message"]["role"] == "assistant"
        assert "rag_trace" in payload["message"]


def test_chat_stream_cancellation_raises_no_contract_drift(monkeypatch) -> None:
    with TestClient(app) as client:
        rag_service = client.app.state.rag_service

        async def cancelled_stream(*args, **kwargs):
            raise asyncio.CancelledError()
            yield  # pragma: no cover

        monkeypatch.setattr(rag_service, "stream_answer", cancelled_stream)

        with client.stream("POST", "/api/v1/chat/stream", json={"message": "cancel"}) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
            assert "event: meta" in body


def test_chat_stream_timeout_is_unified_error(monkeypatch) -> None:
    with TestClient(app) as client:
        rag_service = client.app.state.rag_service

        async def slow_answer(*args, **kwargs):
            await asyncio.sleep(0.2)
            return {
                "session_id": "ses_timeout",
                "message": {
                    "message_id": "msg_timeout",
                    "role": "assistant",
                    "content": "timeout",
                    "timestamp": "2026-04-14T00:00:00Z",
                    "rag_trace": None,
                },
            }

        monkeypatch.setattr(rag_service, "answer", slow_answer)

        resp = client.post("/api/v1/chat", json={"message": "timeout"})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["message"]["content"] == "timeout"
