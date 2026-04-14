from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def _register_admin(client: TestClient) -> str:
    username = f"jobs_admin_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "admin", "admin_code": "letmein"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _register_user(client: TestClient) -> str:
    username = f"jobs_user_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "user"},
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


def test_build_document_creates_queued_job() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        uploaded = _upload_text(client, token, b"build me", filename="build.txt")

        response = client.post(
            f"/api/v1/documents/{uploaded['document_id']}/build",
            headers=_auth_headers(token),
            json={"chunk_strategy": "general"},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["job_id"]
        assert body["document_id"] == uploaded["document_id"]
        assert body["status"] == "queued"


def test_document_job_endpoints_require_admin() -> None:
    with TestClient(app) as client:
        admin_token = _register_admin(client)
        user_token = _register_user(client)
        uploaded = _upload_text(client, admin_token, b"secure", filename="secure.txt")
        job_id = uploaded["job_id"]

        get_resp = client.get(f"/api/v1/documents/jobs/{job_id}", headers=_auth_headers(user_token))
        assert get_resp.status_code == 403
        assert get_resp.json()["code"] == "AUTH_FORBIDDEN"

        stream_resp = client.get(f"/api/v1/documents/jobs/{job_id}/stream", headers=_auth_headers(user_token))
        assert stream_resp.status_code == 403
        assert stream_resp.json()["code"] == "AUTH_FORBIDDEN"

        cancel_resp = client.post(f"/api/v1/documents/jobs/{job_id}/cancel", headers=_auth_headers(user_token))
        assert cancel_resp.status_code == 403
        assert cancel_resp.json()["code"] == "AUTH_FORBIDDEN"


def test_list_and_get_jobs_return_public_fields_only() -> None:
    with TestClient(app) as client:
        token = _register_admin(client)
        uploaded = _upload_text(client, token, b"observe", filename="observe.txt")
        job_id = uploaded["job_id"]

        list_resp = client.get("/api/v1/documents/jobs", headers=_auth_headers(token))
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        job = next(item for item in items if item["job_id"] == job_id)
        assert set(job.keys()) == {
            "job_id",
            "document_id",
            "status",
            "stage",
            "progress",
            "message",
            "error_code",
            "created_at",
            "updated_at",
            "finished_at",
        }

        get_resp = client.get(f"/api/v1/documents/jobs/{job_id}", headers=_auth_headers(token))
        assert get_resp.status_code == 200
        payload = get_resp.json()
        assert set(payload.keys()) == set(job.keys())
        assert payload["job_id"] == job_id
