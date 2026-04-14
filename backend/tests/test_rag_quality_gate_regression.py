from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _register_admin(client: TestClient) -> str:
    username = f"rag_admin_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "admin", "admin_code": "letmein"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_ready_doc(client: TestClient, token: str, text: bytes, filename: str = "seed.txt") -> tuple[str, str]:
    upload = client.post(
        "/api/v1/documents/upload",
        headers=_headers(token),
        files={"file": (filename, text, "text/plain")},
    )
    assert upload.status_code == 202
    payload = upload.json()
    return payload["job_id"], payload["document_id"]


def _wait_job(client: TestClient, token: str, job_id: str) -> dict:
    for _ in range(60):
        resp = client.get(f"/api/v1/documents/jobs/{job_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] in {"succeeded", "failed", "canceled"}:
            return data
    raise AssertionError("job not terminal")


def test_rag_quality_gate_positive_hit() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        job_id, _ = _seed_ready_doc(client, token, b"milvus vector recall and bm25 hybrid retrieval")
        final = _wait_job(client, token, job_id)
        assert final["status"] == "succeeded"

        resp = client.post("/api/v1/chat", json={"message": "hybrid retrieval"})
        assert resp.status_code == 200
        payload = resp.json()
        trace = payload["message"]["rag_trace"]
        assert trace["metrics"]["gate_passed"] is True
        assert len(trace["retrieved"]) >= 1
        assert trace["request_id"].startswith("req_")


def test_rag_quality_gate_rejects_irrelevant_queries() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        job_id, _ = _seed_ready_doc(client, token, b"python async worker queue state machine")
        final = _wait_job(client, token, job_id)
        assert final["status"] == "succeeded"

        irrelevant_queries = [
            "quantum grape nebula banana",
            "medieval pottery taxonomy",
            "oceanic tectonic resonance ritual",
        ]
        for q in irrelevant_queries:
            resp = client.post("/api/v1/chat", json={"message": q})
            assert resp.status_code == 200
            payload = resp.json()
            trace = payload["message"]["rag_trace"]
            assert trace["metrics"]["gate_passed"] is False
            assert trace["retrieved"] == []
            assert trace["request_id"].startswith("req_")
            assert "未检索到足够相关的知识片段" in payload["message"]["content"]


def test_rag_quality_gate_mid_band_fallback_allows_lexical_hit() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        job_id, _ = _seed_ready_doc(client, token, b"deterministic lexical fallback phrase alpha beta")
        final = _wait_job(client, token, job_id)
        assert final["status"] == "succeeded"

        resp = client.post("/api/v1/chat", json={"message": "lexical fallback phrase"})
        assert resp.status_code == 200
        payload = resp.json()
        trace = payload["message"]["rag_trace"]
        assert trace["metrics"]["gate_passed"] is True
        assert trace["metrics"]["lexical_hits"] >= 1
        assert len(trace["retrieved"]) >= 1


def test_rag_quality_gate_stream_consistent_with_chat() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        job_id, _ = _seed_ready_doc(client, token, b"hybrid stream consistency check")
        final = _wait_job(client, token, job_id)
        assert final["status"] == "succeeded"

        with client.stream("POST", "/api/v1/chat/stream", json={"message": "noise gibberish qwerty"}) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
            assert "event: trace" in body
            assert '"gate_passed": false' in body
            assert "event: done" in body
