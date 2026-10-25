import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from cli.openapi import OPENAPI_PATH, render_openapi

EXPECTED = {
    ("get", "/health"),
    ("get", "/api/v1/service-areas"),
    ("get", "/api/v1/service-areas/{service_area_id}"),
    ("get", "/api/v1/service-areas/{service_area_id}/summary"),
    ("get", "/api/v1/service-areas/{service_area_id}/metrics"),
    ("get", "/api/v1/service-areas/{service_area_id}/quality"),
    ("get", "/api/v1/service-areas/{service_area_id}/cells"),
    ("post", "/api/v1/comparisons"),
    ("post", "/api/v1/scoring/preview"),
    ("get", "/api/v1/analysis-runs"),
    ("get", "/api/v1/analysis-runs/{analysis_run_id}"),
    ("get", "/api/v1/scoring-models"),
}


def test_openapi_contains_every_documented_path() -> None:
    with TestClient(create_app()) as c:
        spec = c.get("/openapi.json").json()
    have = {(m, p) for p, ops in spec["paths"].items() for m in ops}
    assert have >= EXPECTED


def test_error_responses_documented_with_unified_shape() -> None:
    spec = create_app().openapi()
    op = spec["paths"]["/api/v1/service-areas/{service_area_id}"]["get"]
    assert op["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )


def test_committed_openapi_matches_app() -> None:
    committed = Path(OPENAPI_PATH)
    assert committed.exists(), "run: uv run python -m cli export-openapi"
    assert json.loads(committed.read_text()) == json.loads(render_openapi()), (
        "docs/openapi.json is stale: run `uv run python -m cli export-openapi`"
    )
