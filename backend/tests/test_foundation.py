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


def test_not_implemented_error_contract_has_request_id() -> None:
    response = client.post("/api/v1/auth/login")
    assert response.status_code == 501
    payload = response.json()
    assert payload["code"] == "NOT_IMPLEMENTED"
    assert payload["message"]
    assert "request_id" in payload
    assert response.headers.get("x-request-id")
