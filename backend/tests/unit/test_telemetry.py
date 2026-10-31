from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.health import HealthResponse
from app.main import create_app


def test_request_headers_and_readiness_status():
    with TestClient(create_app()) as client:
        response = client.get("/missing?private-do-not-log=value")
        assert response.status_code == 404
        assert len(response.headers["x-request-id"]) == 36
        assert response.headers["server-timing"].startswith("app;dur=")
        with patch(
            "app.api.health.health",
            return_value=HealthResponse(status="ok", database="unavailable"),
        ):
            assert client.get("/ready").status_code == 503
        with patch(
            "app.api.health.health", return_value=HealthResponse(status="ok", database="ok")
        ):
            assert client.get("/ready").status_code == 200
