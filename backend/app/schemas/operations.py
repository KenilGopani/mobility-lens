"""Every operational response is explicitly synthetic; geographic scores are separate."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class SimulationRef(BaseModel):
    id: uuid.UUID
    analysis_run_id: uuid.UUID
    seed: int
    generator_version: str
    parameters: dict[str, Any]
    simulated_start_at: datetime
    created_at: datetime
    synthetic: Literal[True] = True


class SimulationPage(BaseModel):
    items: list[SimulationRef]
    total: int
    limit: int
    offset: int
    synthetic: Literal[True] = True


class OperationsDay(BaseModel):
    date: date
    routes: int
    completed: int
    interventions: int
    completion_rate: float | None
    mean_duration_minutes: float | None


class OperationsSummary(BaseModel):
    service_area_id: uuid.UUID
    simulation: SimulationRef
    route_count: int
    completion_rate: float | None
    intervention_rate: float | None
    mean_trip_duration_minutes: float | None
    issue_count: int
    open_issues: int
    resolved_issues: int
    mean_resolution_hours: float | None
    issues_by_severity: dict[str, int]
    days: list[OperationsDay]
    synthetic: Literal[True] = True
    disclaimer: str = "Illustrative synthetic scenario, not real fleet data or a forecast."
