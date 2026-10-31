import uuid
from typing import Any

from sqlalchemy import Date, func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, OperationalIssue, RouteEvent, SimulationRun


def list_simulations(
    session: Session, area_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[SimulationRun], int]:
    base = select(SimulationRun).join(AnalysisRun).where(AnalysisRun.service_area_id == area_id)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(SimulationRun.created_at.desc(), SimulationRun.id).limit(limit).offset(offset)
    )
    return list(rows), total


def get_simulation(
    session: Session, area_id: uuid.UUID, run_id: uuid.UUID | None
) -> SimulationRun | None:
    stmt = select(SimulationRun).join(AnalysisRun).where(AnalysisRun.service_area_id == area_id)
    if run_id is not None:
        stmt = stmt.where(SimulationRun.id == run_id)
    return session.scalar(stmt.order_by(SimulationRun.created_at.desc(), SimulationRun.id).limit(1))


def route_days(session: Session, simulation_id: uuid.UUID) -> list[Any]:
    day = func.timezone("UTC", RouteEvent.started_at).cast(Date)
    return list(
        session.execute(
            select(
                day.label("day"),
                func.count().label("routes"),
                func.count().filter(RouteEvent.completed).label("completed"),
                func.count().filter(RouteEvent.intervention_count > 0).label("interventions"),
                func.sum(RouteEvent.duration_minutes)
                .filter(RouteEvent.completed)
                .label("duration_sum"),
            )
            .where(RouteEvent.simulation_run_id == simulation_id)
            .group_by(day)
            .order_by(day)
        )
    )


def issue_stats(session: Session, simulation_id: uuid.UUID) -> list[Any]:
    hours = (
        func.extract("epoch", OperationalIssue.resolved_at - OperationalIssue.created_at) / 3600.0
    )
    return list(
        session.execute(
            select(
                OperationalIssue.severity,
                OperationalIssue.status,
                func.count().label("count"),
                func.sum(hours).label("resolution_hours"),
            )
            .where(OperationalIssue.simulation_run_id == simulation_id)
            .group_by(OperationalIssue.severity, OperationalIssue.status)
        )
    )
