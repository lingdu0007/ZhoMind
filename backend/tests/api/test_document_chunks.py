from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _register_admin(client: TestClient) -> str:
    username = f"chunks_admin_{uuid4().hex[:8]}"
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
    return response.json()


def _poll_job(client: TestClient, token: str, job_id: str, timeout_sec: float = 5.0) -> dict:
    import time

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


def test_document_chunks_return_409_when_not_ready() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        uploaded = _upload_text(client, token, b"not ready yet", filename="not-ready.txt")

        response = client.get(
            f"/api/v1/documents/{uploaded['document_id']}/chunks",
            headers=_auth_headers(token),
        )
        assert response.status_code == 409
        assert response.json()["code"] == "DOC_CHUNK_RESULT_NOT_READY"


def test_document_chunks_return_paginated_items() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        uploaded = _upload_text(client, token, b"alpha beta gamma delta epsilon", filename="ready.txt")
        final_job = _poll_job(client, token, uploaded["job_id"])
        assert final_job["status"] == "succeeded"

        response = client.get(
            f"/api/v1/documents/{uploaded['document_id']}/chunks?page=1&page_size=10",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload["items"], list)
        assert payload["pagination"]["page"] == 1
        assert payload["pagination"]["page_size"] == 10
        assert payload["pagination"]["total"] >= 1
        assert payload["items"]
