from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_ok_shape(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "unavailable"}


def test_health_degrades_gracefully_when_db_unavailable() -> None:
    # Port 1 is never a Postgres server; the endpoint must still return 200.
    settings = Settings(database_url="postgresql+psycopg://x:y@127.0.0.1:1/none")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "unavailable"}


def test_cors_allows_only_configured_origin() -> None:
    settings = Settings(cors_origins=["http://localhost:5173"])
    with TestClient(create_app(settings)) as client:
        allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
        denied = client.get("/health", headers={"Origin": "http://evil.example"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
