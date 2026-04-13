from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_prefix_not_404() -> None:
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "pagination" in payload


def test_auth_login_contract_200_and_401() -> None:
    ok = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin-token"})
    assert ok.status_code == 200
    ok_payload = ok.json()
    assert ok_payload["token_type"] == "Bearer"
    assert ok_payload["role"] == "admin"

    bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    assert bad.status_code == 401
    bad_payload = bad.json()
    assert bad_payload["code"] == "AUTH_BAD_CREDENTIALS"
    assert "request_id" in bad_payload
