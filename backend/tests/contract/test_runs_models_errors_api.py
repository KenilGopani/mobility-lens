import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.middleware import MAX_BODY_BYTES
from app.schemas.api import AnalysisRunOut, AnalysisRunPage, ScoringModelList
from tests.contract.conftest import World
from tests.contract.test_service_areas_api import assert_error

pytestmark = pytest.mark.integration
RUNS = "/api/v1/analysis-runs"


def test_runs_list_order_and_total(client: TestClient, world: World) -> None:
    page = AnalysisRunPage.model_validate(client.get(RUNS).json())
    assert page.total == 6 and len(page.items) == 6
    started = [r.started_at for r in page.items]
    assert started == sorted(started, reverse=True)
    assert client.get(RUNS).json() == client.get(RUNS).json()


def test_runs_filters_and_pagination(client: TestClient, world: World) -> None:
    alpha = client.get(RUNS, params={"service_area_id": str(world.ids["Alpha"])}).json()
    assert [r["id"] for r in alpha["items"]] == [str(world.alpha_run), str(world.alpha_old_run)]
    failed = client.get(RUNS, params={"status": "failed"}).json()
    assert [r["id"] for r in failed["items"]] == [str(world.epsilon_failed_run)]
    assert failed["items"][0]["error_message"] == "boom"
    none = client.get(
        RUNS, params={"service_area_id": str(world.ids["Beta"]), "status": "failed"}
    ).json()
    assert none["items"] == [] and none["total"] == 0
    p = client.get(RUNS, params={"limit": 4, "offset": 4}).json()
    assert len(p["items"]) == 2 and p["total"] == 6


@pytest.mark.parametrize(
    "params", [{"status": "bogus"}, {"service_area_id": "x"}, {"limit": 201}, {"offset": -1}]
)
def test_runs_list_validation(client: TestClient, params: dict[str, object]) -> None:
    assert_error(client.get(RUNS, params=params), 422, "validation_error")


def test_run_detail(client: TestClient, world: World) -> None:
    r = client.get(f"{RUNS}/{world.alpha_run}")
    assert r.status_code == 200
    run = AnalysisRunOut.model_validate(r.json())
    assert run.service_area_id == world.ids["Alpha"] and run.source_metadata == {"osm": "fixture"}
    assert run.parameters == {"h3_resolution": 9}
    assert_error(client.get(f"{RUNS}/{uuid.uuid4()}"), 404, "not_found")
    assert_error(client.get(f"{RUNS}/nope"), 422, "validation_error")


def test_scoring_models(client: TestClient, world: World) -> None:
    r = client.get("/api/v1/scoring-models")
    assert r.status_code == 200
    models = ScoringModelList.model_validate(r.json()).items
    assert [(m.name, m.is_default) for m in models] == [("baseline", True)]
    assert sum(models[0].weights.values()) == pytest.approx(1.0)


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    assert_error(client.get("/api/v1/nope"), 404, "not_found")


def test_method_not_allowed_uses_error_shape(client: TestClient) -> None:
    assert_error(client.delete("/api/v1/service-areas"), 405, "method_not_allowed")


def test_body_size_limit(client: TestClient) -> None:
    big = {"service_area_ids": [], "pad": "x" * (MAX_BODY_BYTES + 10)}
    assert_error(client.post("/api/v1/comparisons", json=big), 413, "payload_too_large")


def test_malformed_json_is_validation_error(client: TestClient) -> None:
    r = client.post(
        "/api/v1/comparisons", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert_error(r, 422, "validation_error")


def test_unhandled_error_does_not_leak_internals(world: World, session) -> None:  # type: ignore[no-untyped-def]
    from app.db.session import get_session
    from app.main import create_app

    app = create_app()

    def broken():  # type: ignore[no-untyped-def]
        raise RuntimeError("secret password=hunter2")
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = broken
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/service-areas")
    assert_error(r, 500, "internal")
    assert "hunter2" not in r.text and "Traceback" not in r.text


def test_cors_stays_narrow(client: TestClient) -> None:
    ok = client.get("/api/v1/scoring-models", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/api/v1/scoring-models", headers={"Origin": "http://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
