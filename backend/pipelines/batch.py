"""Serial batch execution with explicit recovery; every attempt retains its own run record."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories import analysis_runs, service_areas
from pipelines.analyze import PIPELINE_VERSION, AnalysisSummary, analyze_area


@dataclass
class BatchResult:
    succeeded: list[AnalysisSummary] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def analyze_all(session: Session, *, resume: bool = False) -> BatchResult:
    """Resume skips successful runs at the same pipeline version/resolution.

    This is recovery of a batch, not a freshness check. Omit resume after changing boundaries,
    definitions, model settings or public source data. Failures never prevent later areas.
    """
    areas = [(a.id, a.slug) for a in service_areas.list_light(session)]
    if not areas:
        raise ValueError("No service areas configured; run seed-service-areas first")
    result = BatchResult()
    for area_id, slug in areas:
        previous = analysis_runs.latest_succeeded_for_area(session, area_id) if resume else None
        if (
            previous is not None
            and previous.pipeline_version == PIPELINE_VERSION
            and previous.parameters.get("h3_resolution") == get_settings().h3_resolution
        ):
            result.skipped.append(slug)
            continue
        try:
            result.succeeded.append(analyze_area(session, slug))
        except Exception as exc:
            session.rollback()
            result.failed[slug] = f"{type(exc).__name__}: {exc}"
    return result
