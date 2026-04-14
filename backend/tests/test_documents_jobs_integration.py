import asyncio
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _register_admin(client: TestClient) -> str:
    username = f"docs_jobs_admin_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "admin", "admin_code": "letmein"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_text(client: TestClient, token: str, content: bytes, filename: str = "doc.txt") -> dict:
    response = client.post(
        "/api/v1/documents/upload",
        headers=_auth_headers(token),
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["job_id"]
    assert payload["document_id"]
    return payload


def _poll_job_until_terminal(client: TestClient, token: str, job_id: str, timeout_sec: float = 5.0) -> tuple[dict, list[str]]:
    deadline = time.time() + timeout_sec
    seen_stages: list[str] = []
    last_payload: dict | None = None

    while time.time() < deadline:
        response = client.get(f"/api/v1/documents/jobs/{job_id}", headers=_auth_headers(token))
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload

        stage = payload["stage"]
        if not seen_stages or seen_stages[-1] != stage:
            seen_stages.append(stage)

        if payload["status"] in {"succeeded", "failed", "canceled"}:
            return payload, seen_stages

        time.sleep(0.05)

    raise AssertionError(f"job {job_id} not finished before timeout, last_payload={last_payload}")


def test_documents_jobs_success_pipeline_to_ready_and_chunks(monkeypatch) -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        service = client.app.state.document_service
        original_parsing = service._parsing
        original_chunking = service._chunking
        original_embedding = service._embedding

        async def slow_parsing(job_id: str):
            await asyncio.sleep(0.08)
            return await original_parsing(job_id)

        async def slow_chunking(job_id: str, text: str):
            await asyncio.sleep(0.08)
            return await original_chunking(job_id, text)

        async def slow_embedding(job_id: str, chunks: list[dict]):
            await asyncio.sleep(0.08)
            await original_embedding(job_id, chunks)

        monkeypatch.setattr(service, "_parsing", slow_parsing)
        monkeypatch.setattr(service, "_chunking", slow_chunking)
        monkeypatch.setattr(service, "_embedding", slow_embedding)

        accepted = _upload_text(client, token, b"line1\nline2\nline3")
        job_id = accepted["job_id"]
        document_id = accepted["document_id"]

        final_job, seen_stages = _poll_job_until_terminal(client, token, job_id)

        assert final_job["status"] == "succeeded"
        assert final_job["stage"] == "completed"
        assert final_job["progress"] == 100
        assert len(seen_stages) >= 3

        docs_resp = client.get("/api/v1/documents", headers=_auth_headers(token))
        assert docs_resp.status_code == 200
        docs_payload = docs_resp.json()
        doc = next(item for item in docs_payload["items"] if item["document_id"] == document_id)
        assert doc["status"] == "ready"

        chunks_resp = client.get(f"/api/v1/documents/{document_id}/chunks", headers=_auth_headers(token))
        assert chunks_resp.status_code == 200
        chunks_payload = chunks_resp.json()
        assert chunks_payload["items"]
        assert chunks_payload["pagination"]["total"] >= 1


def test_documents_jobs_failure_sets_document_failed_and_error_code() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        accepted = _upload_text(client, token, b"   \n\n\t\n", filename="empty.txt")
        job_id = accepted["job_id"]
        document_id = accepted["document_id"]

        final_job, _ = _poll_job_until_terminal(client, token, job_id)

        assert final_job["status"] == "failed"
        assert final_job["stage"] == "failed"
        assert final_job["error_code"] == "DOC_PARSE_ERROR"

        docs_resp = client.get("/api/v1/documents", headers=_auth_headers(token))
        assert docs_resp.status_code == 200
        doc = next(item for item in docs_resp.json()["items"] if item["document_id"] == document_id)
        assert doc["status"] == "failed"

        chunks_resp = client.get(f"/api/v1/documents/{document_id}/chunks", headers=_auth_headers(token))
        assert chunks_resp.status_code == 409
        chunks_err = chunks_resp.json()
        assert chunks_err["code"] == "DOC_CHUNK_RESULT_NOT_READY"

        with client.stream(
            "GET",
            f"/api/v1/documents/jobs/{job_id}/stream",
            headers=_auth_headers(token),
        ) as sse_resp:
            assert sse_resp.status_code == 200
            body = "".join(line for line in sse_resp.iter_text())
            assert "event: error" in body
            assert "DOC_PARSE_ERROR" in body
            assert '"status": "failed"' in body


def test_documents_jobs_cancel_running_and_finished_conflict(monkeypatch) -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        service = client.app.state.document_service
        original_parsing = service._parsing

        async def slow_parsing(job_id: str):
            await asyncio.sleep(0.3)
            return await original_parsing(job_id)

        monkeypatch.setattr(service, "_parsing", slow_parsing)

        accepted = _upload_text(client, token, b"cancel-me")
        job_id = accepted["job_id"]
        document_id = accepted["document_id"]

        cancel_resp = client.post(f"/api/v1/documents/jobs/{job_id}/cancel", headers=_auth_headers(token))
        assert cancel_resp.status_code == 202
        assert cancel_resp.json()["status"] == "canceled"

        final_job, _ = _poll_job_until_terminal(client, token, job_id)
        assert final_job["status"] == "canceled"

        # 列表过滤：status + document_id
        list_by_status = client.get("/api/v1/documents/jobs", params={"status": "canceled"}, headers=_auth_headers(token))
        assert list_by_status.status_code == 200
        status_items = list_by_status.json()["items"]
        assert any(item["job_id"] == job_id for item in status_items)

        list_by_doc = client.get("/api/v1/documents/jobs", params={"document_id": document_id}, headers=_auth_headers(token))
        assert list_by_doc.status_code == 200
        doc_items = list_by_doc.json()["items"]
        assert any(item["job_id"] == job_id for item in doc_items)

        # 已完成任务不可取消
        accepted2 = _upload_text(client, token, b"done")
        succeeded_job, _ = _poll_job_until_terminal(client, token, accepted2["job_id"])
        assert succeeded_job["status"] == "succeeded"

        conflict_resp = client.post(f"/api/v1/documents/jobs/{accepted2['job_id']}/cancel", headers=_auth_headers(token))
        assert conflict_resp.status_code == 409
        assert conflict_resp.json()["code"] == "DOC_JOB_STATE_CONFLICT"


def test_documents_jobs_list_pagination_boundaries() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        created_job_ids: list[str] = []
        for idx in range(5):
            accepted = _upload_text(client, token, f"doc-{idx}".encode("utf-8"), filename=f"d{idx}.txt")
            created_job_ids.append(accepted["job_id"])

        for job_id in created_job_ids:
            _poll_job_until_terminal(client, token, job_id)

        page1 = client.get("/api/v1/documents/jobs", params={"page": 1, "page_size": 2}, headers=_auth_headers(token))
        assert page1.status_code == 200
        page1_payload = page1.json()
        assert page1_payload["pagination"]["page"] == 1
        assert page1_payload["pagination"]["page_size"] == 2
        assert page1_payload["pagination"]["total"] >= 5
        assert len(page1_payload["items"]) == 2

        page3 = client.get("/api/v1/documents/jobs", params={"page": 3, "page_size": 2}, headers=_auth_headers(token))
        assert page3.status_code == 200
        page3_payload = page3.json()
        assert page3_payload["pagination"]["page"] == 3
        assert page3_payload["pagination"]["page_size"] == 2
        assert page3_payload["pagination"]["total"] == page1_payload["pagination"]["total"]
        assert len(page3_payload["items"]) >= 1

        beyond = client.get("/api/v1/documents/jobs", params={"page": 999, "page_size": 2}, headers=_auth_headers(token))
        assert beyond.status_code == 200
        beyond_payload = beyond.json()
        assert beyond_payload["pagination"]["page"] == 999
        assert beyond_payload["pagination"]["page_size"] == 2
        assert beyond_payload["pagination"]["total"] == page1_payload["pagination"]["total"]
        assert beyond_payload["items"] == []


def test_documents_jobs_batch_build_returns_partial_failures_without_swallowing() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        ok_doc = _upload_text(client, token, b"ok-batch", filename="ok-batch.txt")
        _poll_job_until_terminal(client, token, ok_doc["job_id"])

        batch_resp = client.post(
            "/api/v1/documents/batch-build",
            headers=_auth_headers(token),
            json={
                "document_ids": [ok_doc["document_id"], "doc_not_exists"],
                "chunk_strategy": "general",
            },
        )
        assert batch_resp.status_code == 202
        payload = batch_resp.json()
        assert "items" in payload
        assert "failed_items" in payload

        assert any(item["document_id"] == ok_doc["document_id"] for item in payload["items"])
        assert any(item["document_id"] == "doc_not_exists" for item in payload["failed_items"])

        failed = next(item for item in payload["failed_items"] if item["document_id"] == "doc_not_exists")
        assert failed["error_code"] == "RESOURCE_NOT_FOUND"
        assert failed["message"]
        assert "detail" in failed
