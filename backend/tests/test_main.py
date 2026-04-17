from fastapi.testclient import TestClient

from backend.main import app


def test_health_exposes_workspace_and_response_headers(monkeypatch) -> None:
    async def _no_seed():
        return None

    monkeypatch.setattr("backend.main.supabase_storage.seed_placeholder_if_empty", _no_seed)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["x-vacay-workspace"]
    assert response.headers["x-vacay-config"]
    payload = response.json()
    assert payload["workspace"]
    assert payload["config_path"]


def test_cors_allows_localhost_and_loopback_dev_ports(monkeypatch) -> None:
    async def _no_seed():
        return None

    monkeypatch.setattr("backend.main.supabase_storage.seed_placeholder_if_empty", _no_seed)

    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://127.0.0.1:3004",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3004"
