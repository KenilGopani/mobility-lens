"""Transactional scenario generation for the CLI only; never invoked by HTTP reads."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OperationalIssue, RouteEvent, SimulationRun
from app.repositories import analysis_runs, service_areas
from pipelines.synthetic import GENERATOR_VERSION, generate_events


def create_simulation(
    session: Session, slug: str, *, seed: int = 42, routes: int = 500
) -> SimulationRun:
    area = service_areas.get_by_slug(session, slug)
    if area is None:
        raise ValueError(f"Unknown service area: {slug}")
    analysis = analysis_runs.latest_succeeded_for_area(session, area.id)
    if analysis is None:
        raise ValueError("A successful geospatial analysis is required before simulation")
    start = (analysis.completed_at or analysis.started_at).astimezone(UTC)
    events, issues = generate_events(seed, routes, start)
    key = hashlib.sha256(
        json.dumps([str(analysis.id), seed, routes, GENERATOR_VERSION, start.isoformat()]).encode()
    ).hexdigest()
    existing = session.scalar(select(SimulationRun).where(SimulationRun.scenario_key == key))
    if existing:
        return existing
    run = SimulationRun(
        analysis_run_id=analysis.id,
        scenario_key=key,
        seed=seed,
        generator_version=GENERATOR_VERSION,
        parameters={
            "routes": routes,
            "distribution": "illustrative-v1",
            "time_basis": "UTC",
            "seeded_at": datetime.now(UTC).isoformat(),
        },
        simulated_start_at=start,
        is_synthetic=True,
    )
    session.add(run)
    session.flush()
    session.add_all(
        RouteEvent(simulation_run_id=run.id, **asdict(event), is_synthetic=True) for event in events
    )
    session.add_all(
        OperationalIssue(simulation_run_id=run.id, **asdict(issue), is_synthetic=True)
        for issue in issues
    )
    session.flush()
    return run
