from fastapi.testclient import TestClient

from src.main import app


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer admin-token"}


def test_chat_sync_real_chain_response_shape() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/chat", json={"message": "keyword"})
        assert resp.status_code == 200
        payload = resp.json()
        assert "session_id" in payload
        assert "message" in payload
        assert payload["message"]["role"] == "assistant"
        assert "rag_trace" in payload["message"]
        assert "metrics" in payload["message"]["rag_trace"]


def test_chat_stream_real_chain_sse_contract() -> None:
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "hello stream rag"},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(line for line in resp.iter_text())
            assert "event: meta" in body
            assert "event: rag_step" in body
            assert "event: content" in body
            assert "event: trace" in body
            assert "event: done" in body


def test_chat_stream_error_shape_stable(monkeypatch) -> None:
    with TestClient(app) as client:
        rag_service = client.app.state.rag_service

        async def broken_stream(*args, **kwargs):
            raise RuntimeError("boom")
            yield  # pragma: no cover

        monkeypatch.setattr(rag_service, "stream_answer", broken_stream)

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "trigger error"},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(line for line in resp.iter_text())
            assert "event: error" in body
            assert '"code": "INTERNAL_ERROR"' in body
            assert '"request_id":' in body
            assert "event: done" in body
