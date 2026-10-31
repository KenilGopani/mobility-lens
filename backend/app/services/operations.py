import uuid

from sqlalchemy.orm import Session

from app.models import SimulationRun
from app.repositories import operations, service_areas
from app.schemas.operations import OperationsDay, OperationsSummary, SimulationPage, SimulationRef
from app.services.errors import NotFoundError


def _area_exists(session: Session, area_id: uuid.UUID) -> None:
    if service_areas.get_light(session, area_id) is None:
        raise NotFoundError("Service area not found")


def run_ref(run: SimulationRun) -> SimulationRef:
    return SimulationRef.model_validate(run, from_attributes=True)


def list_runs(session: Session, area_id: uuid.UUID, limit: int, offset: int) -> SimulationPage:
    _area_exists(session, area_id)
    rows, total = operations.list_simulations(session, area_id, limit, offset)
    return SimulationPage(items=[run_ref(r) for r in rows], total=total, limit=limit, offset=offset)


def summary(
    session: Session, area_id: uuid.UUID, simulation_run_id: uuid.UUID | None
) -> OperationsSummary:
    _area_exists(session, area_id)
    run = operations.get_simulation(session, area_id, simulation_run_id)
    if run is None:
        raise NotFoundError("No synthetic simulation for this service area; run simulate-area")
    days = operations.route_days(session, run.id)
    routes = sum(d.routes for d in days)
    completed = sum(d.completed for d in days)
    interventions = sum(d.interventions for d in days)
    duration = sum(float(d.duration_sum or 0) for d in days)
    issues = operations.issue_stats(session, run.id)
    by_severity = dict.fromkeys(["info", "warning", "critical"], 0)
    for i in issues:
        by_severity[i.severity] += i.count
    resolved = sum(i.count for i in issues if i.status == "resolved")
    open_count = sum(i.count for i in issues if i.status == "open")
    resolution_hours = sum(float(i.resolution_hours or 0) for i in issues)
    return OperationsSummary(
        service_area_id=area_id,
        simulation=run_ref(run),
        route_count=routes,
        completion_rate=completed / routes if routes else None,
        intervention_rate=interventions / routes if routes else None,
        mean_trip_duration_minutes=duration / completed if completed else None,
        issue_count=resolved + open_count,
        open_issues=open_count,
        resolved_issues=resolved,
        mean_resolution_hours=resolution_hours / resolved if resolved else None,
        issues_by_severity=by_severity,
        days=[
            OperationsDay(
                date=d.day,
                routes=d.routes,
                completed=d.completed,
                interventions=d.interventions,
                completion_rate=d.completed / d.routes if d.routes else None,
                mean_duration_minutes=float(d.duration_sum) / d.completed if d.completed else None,
            )
            for d in days
        ],
    )
