import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import OperationalIssue, RouteEvent, SimulationRun
from pipelines.analyze import analyze_area
from pipelines.simulation import create_simulation
from tests.integration.test_analyze import fixture_provider, seeded  # noqa: F401

pytestmark = pytest.mark.integration


def test_simulation_repeats_without_duplicates_and_is_synthetic(session: Session, seeded: str):  # noqa: F811
    analyze_area(session, seeded, network_provider=fixture_provider)
    first = create_simulation(session, seeded, seed=23, routes=100)
    again = create_simulation(session, seeded, seed=23, routes=100)
    assert first.id == again.id
    assert first.is_synthetic and first.seed == 23
    assert session.scalar(select(func.count()).select_from(RouteEvent)) == 100
    assert session.scalar(select(func.count()).select_from(SimulationRun)) == 1
    assert all(r.is_synthetic for r in session.scalars(select(RouteEvent)))
    assert all(i.is_synthetic for i in session.scalars(select(OperationalIssue)))
    with pytest.raises(IntegrityError), session.begin_nested():
        first.is_synthetic = False
        session.flush()


def test_simulation_requires_successful_geospatial_analysis(session: Session, seeded: str):  # noqa: F811
    with pytest.raises(ValueError, match="successful geospatial"):
        create_simulation(session, seeded)


def test_operations_summary_matches_events_and_preserves_scores(session: Session, seeded: str):  # noqa: F811
    from app.models import AreaScore
    from app.services.operations import summary

    analysis = analyze_area(session, seeded, network_provider=fixture_provider)
    before = session.scalar(select(AreaScore.score))
    run = create_simulation(session, seeded, seed=42, routes=200)
    result = summary(session, analysis.service_area_id, run.id)
    events = list(session.scalars(select(RouteEvent)))
    completed = [e for e in events if e.completed]
    issues = list(session.scalars(select(OperationalIssue)))
    resolved = [i for i in issues if i.resolved_at is not None]
    assert result.synthetic and result.simulation.synthetic
    assert result.route_count == 200
    assert result.completion_rate == pytest.approx(len(completed) / 200)
    assert result.intervention_rate == pytest.approx(
        sum(e.intervention_count > 0 for e in events) / 200
    )
    assert result.mean_trip_duration_minutes == pytest.approx(
        sum(e.duration_minutes for e in completed) / len(completed)
    )
    assert result.issue_count == len(issues) == sum(result.issues_by_severity.values())
    assert result.mean_resolution_hours == pytest.approx(
        sum((i.resolved_at - i.created_at).total_seconds() / 3600 for i in resolved) / len(resolved)
    )
    assert sum(d.routes for d in result.days) == 200
    assert session.scalar(select(AreaScore.score)) == before


def test_operations_http_contract_and_unknown_scenario(session: Session, seeded: str):  # noqa: F811
    import uuid

    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.main import create_app

    analysis = analyze_area(session, seeded, network_provider=fixture_provider)
    create_simulation(session, seeded, routes=10)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        base = f"/api/v1/service-areas/{analysis.service_area_id}"
        listing = client.get(f"{base}/simulations").json()
        assert listing["synthetic"] is True and listing["items"][0]["synthetic"] is True
        response = client.get(f"{base}/operations")
        assert response.status_code == 200
        assert response.json()["synthetic"] is True
        assert response.json()["route_count"] == 10
        assert client.get(f"{base}/operations?simulation_run_id={uuid.uuid4()}").status_code == 404
        assert client.get(f"{base}/simulations?limit=201").status_code == 422


def test_resolved_issue_requires_resolution_timestamp(session: Session, seeded: str):  # noqa: F811
    from datetime import UTC, datetime

    analyze_area(session, seeded, network_provider=fixture_provider)
    run = create_simulation(session, seeded, routes=10)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            OperationalIssue(
                simulation_run_id=run.id,
                category="test",
                severity="warning",
                status="resolved",
                created_at=datetime.now(UTC),
                resolved_at=None,
                is_synthetic=True,
            )
        )
        session.flush()
