"""Pure, deterministic synthetic events. These distributions are illustrations, not forecasts."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

GENERATOR_VERSION = "v1"


@dataclass(frozen=True)
class SimulatedRoute:
    route_id: str
    started_at: datetime
    ended_at: datetime
    distance_km: float
    duration_minutes: float
    completed: bool
    intervention_count: int


@dataclass(frozen=True)
class SimulatedIssue:
    category: str
    severity: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


def generate_events(
    seed: int, routes: int, start: datetime
) -> tuple[list[SimulatedRoute], list[SimulatedIssue]]:
    if not 1 <= routes <= 100_000:
        raise ValueError("routes must be between 1 and 100000")
    if not 0 <= seed <= 2_147_483_647:
        raise ValueError("seed must be between 0 and 2147483647")
    if start.tzinfo is None:
        raise ValueError("simulated start time must include a timezone")
    rng = random.Random(seed)
    events, issues = [], []
    for i in range(routes):
        when = start + timedelta(minutes=i * 15)
        distance = round(rng.uniform(1, 25), 3)
        duration = round(distance / rng.uniform(12, 35) * 60, 3)
        interventions = rng.choices([0, 1, 2], weights=[85, 12, 3])[0]
        completed = rng.random() < 0.92
        events.append(
            SimulatedRoute(
                f"sim-{i:06d}",
                when,
                when + timedelta(minutes=duration),
                distance,
                duration,
                completed,
                interventions,
            )
        )
        if rng.random() < 0.12:
            resolved = rng.random() < 0.75
            issues.append(
                SimulatedIssue(
                    rng.choice(["routing", "service-delay", "data-review"]),
                    rng.choices(["info", "warning", "critical"], weights=[30, 60, 10])[0],
                    "resolved" if resolved else "open",
                    when,
                    when + timedelta(hours=round(rng.uniform(0.5, 72), 3)) if resolved else None,
                )
            )
    return events, issues
