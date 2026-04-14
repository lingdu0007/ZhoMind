from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def test_register_login_me_flow() -> None:
    username = f"admin_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        register = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "secret123", "role": "admin", "admin_code": "letmein"},
        )
        assert register.status_code == 200
        register_payload = register.json()
        assert register_payload["token_type"] == "bearer"
        assert register_payload["username"] == username
        assert register_payload["role"] == "admin"
        token = register_payload["access_token"]

        login = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "secret123"},
        )
        assert login.status_code == 200
        login_payload = login.json()
        assert login_payload["username"] == username
        assert login_payload["role"] == "admin"
        assert login_payload["token_type"] == "bearer"

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        assert me.json() == {"username": username, "role": "admin"}


def test_register_requires_admin_code_for_admin() -> None:
    username = f"bad_admin_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "secret123", "role": "admin"},
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["code"] == "ADMIN_CODE_REQUIRED"
        assert "request_id" in payload


def test_me_requires_bearer_token() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        payload = response.json()
        assert payload["code"] == "AUTH_INVALID_TOKEN"
        assert "request_id" in payload


def test_admin_guard_rejects_non_admin_document_access() -> None:
    username = f"user_{uuid4().hex[:8]}"

    with TestClient(app) as client:
        register = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "secret123", "role": "user"},
        )
        assert register.status_code == 200
        token = register.json()["access_token"]

        response = client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["code"] == "AUTH_FORBIDDEN"
        assert "request_id" in payload
