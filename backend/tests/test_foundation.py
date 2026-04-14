from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_prefix_not_404() -> None:
    username = f"foundation_{uuid4().hex[:8]}"

    with TestClient(app) as local_client:
        register = local_client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "secret123", "role": "user"},
        )
        assert register.status_code == 200
        token = register.json()["access_token"]

        response = local_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "items" in payload


def test_auth_login_contract_200_and_401() -> None:
    username = f"login_{uuid4().hex[:8]}"

    with TestClient(app) as local_client:
        register = local_client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "secret123", "role": "admin", "admin_code": "letmein"},
        )
        assert register.status_code == 200

        ok = local_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "secret123"},
        )
        assert ok.status_code == 200
        ok_payload = ok.json()
        assert ok_payload["token_type"] == "bearer"
        assert ok_payload["role"] == "admin"

        bad = local_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "bad"},
        )
        assert bad.status_code == 401
        bad_payload = bad.json()
        assert bad_payload["code"] == "AUTH_BAD_CREDENTIALS"
        assert "request_id" in bad_payload
