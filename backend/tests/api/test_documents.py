from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _register_admin(client: TestClient) -> str:
    username = f"docs_admin_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "admin", "admin_code": "letmein"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _poll_job(client: TestClient, token: str, job_id: str, timeout_sec: float = 5.0) -> dict:
    deadline = time.time() + timeout_sec
    last_payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/documents/jobs/{job_id}", headers=_auth_headers(token))
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["status"] in {"succeeded", "failed", "canceled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} not finished before timeout, last_payload={last_payload}")


def test_documents_upload_list_delete_metadata_flow() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)

        upload = client.post(
            "/api/v1/documents/upload",
            headers=_auth_headers(token),
            files={"file": ("guide.txt", b"alpha beta gamma", "text/plain")},
        )
        assert upload.status_code == 202
        accepted = upload.json()
        assert accepted["status"] == "queued"
        assert accepted["document_id"]
        assert accepted["job_id"]

        final_job = _poll_job(client, token, accepted["job_id"])
        assert final_job["status"] == "succeeded"

        listed = client.get("/api/v1/documents", headers=_auth_headers(token))
        assert listed.status_code == 200
        items = listed.json()["items"]
        row = next(item for item in items if item["document_id"] == accepted["document_id"])
        assert row["filename"] == "guide.txt"
        assert row["file_type"] == "text/plain"
        assert row["file_size"] == len(b"alpha beta gamma")
        assert row["status"] == "ready"
        assert row["chunk_strategy"] == "general"
        assert row["chunk_count"] >= 1
        assert row["uploaded_at"]

        delete_response = client.delete(f"/api/v1/documents/{row['filename']}", headers=_auth_headers(token))
        assert delete_response.status_code == 204

        listed_after_delete = client.get("/api/v1/documents", headers=_auth_headers(token))
        assert listed_after_delete.status_code == 200
        remaining_ids = {item["document_id"] for item in listed_after_delete.json()["items"]}
        assert accepted["document_id"] not in remaining_ids


def test_documents_list_filters_by_status() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)

        upload = client.post(
            "/api/v1/documents/upload",
            headers=_auth_headers(token),
            files={"file": ("blank.txt", b"   \n\t", "text/plain")},
        )
        assert upload.status_code == 202
        accepted = upload.json()

        final_job = _poll_job(client, token, accepted["job_id"])
        assert final_job["status"] == "failed"

        failed_list = client.get(
            "/api/v1/documents",
            params={"status": "failed"},
            headers=_auth_headers(token),
        )
        assert failed_list.status_code == 200
        failed_ids = {item["document_id"] for item in failed_list.json()["items"]}
        assert accepted["document_id"] in failed_ids
