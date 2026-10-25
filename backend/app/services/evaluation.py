"""Shared read-side evaluation: score areas from stored area metrics via app.scoring.

No scoring math lives here; this module loads data in bulk (a fixed number of queries,
independent of the number of areas), delegates to ``score_area`` and shapes results.
"""

import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AnalysisRun, AreaMetric, MetricDefinition, ScoringModel, ServiceArea
from app.quality.rules import peer_outlier_findings
from app.repositories import analysis_runs, metric_definitions, metrics, scoring_models
from app.schemas.api import (
    MetricHighlight,
    PeerOutlier,
    RunRef,
    ScoreComponent,
    ScoringModelRef,
)
from app.scoring.engine import MetricInput, ScoreResult, score_area
from app.services.errors import NotFoundError

HIGHLIGHT_COUNT = 2
RANK_PRECISION = 6  # scores equal to 6 decimals tie (guards float noise)
NO_SUCCESSFUL_RUN = "no_successful_run"


@dataclass
class Evaluated:
    area: ServiceArea
    run: AnalysisRun | None
    metrics: Mapping[str, AreaMetric]
    result: ScoreResult | None
    rank: int | None = None


def default_model(session: Session) -> ScoringModel | None:
    return scoring_models.get_default(session)


def model_ref(model: ScoringModel) -> ScoringModelRef:
    return ScoringModelRef(
        id=model.id,
        name=model.name,
        version=model.version,
        weights={k: float(v) for k, v in model.weights.items()},
    )


def get_model_or_404(session: Session, model_id: uuid.UUID) -> ScoringModel:
    model = session.get(ScoringModel, model_id)
    if model is None:
        raise NotFoundError("Scoring model not found", {"scoring_model_id": str(model_id)})
    return model


def run_ref(run: AnalysisRun | None) -> RunRef | None:
    if run is None:
        return None
    return RunRef(
        id=run.id,
        status=run.status,
        pipeline_version=run.pipeline_version,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def dense_ranks(scores: list[float | None]) -> list[int | None]:
    """Dense ranking, higher score first; ties share a rank; None stays unranked."""
    distinct = sorted({round(s, RANK_PRECISION) for s in scores if s is not None}, reverse=True)
    position = {s: i + 1 for i, s in enumerate(distinct)}
    return [None if s is None else position[round(s, RANK_PRECISION)] for s in scores]


def evaluate_areas(
    session: Session,
    areas: list[ServiceArea],
    weights: Mapping[str, float],
    required_metrics: Collection[str] | None = None,
) -> list[Evaluated]:
    """Score each area's latest succeeded run (bulk-loaded) and rank within the given set."""
    area_list = areas
    runs = analysis_runs.latest_succeeded_for_areas(session, [a.id for a in area_list])
    by_run = metrics.area_metrics_for_runs(session, [r.id for r in runs.values()])
    out: list[Evaluated] = []
    for area in area_list:
        run = runs.get(area.id)
        if run is None:
            out.append(Evaluated(area, None, {}, None))
            continue
        area_metrics = by_run.get(run.id, {})
        result = score_area(
            {
                k: MetricInput(m.normalized_value, m.confidence, m.raw_value)
                for k, m in area_metrics.items()
            },
            weights,
            required_metrics=required_metrics,
        )
        out.append(Evaluated(area, run, area_metrics, result))
    ranks = dense_ranks([e.result.score if e.result else None for e in out])
    for e, r in zip(out, ranks, strict=True):
        e.rank = r
    return out


def components_out(
    result: ScoreResult, defs: Mapping[str, MetricDefinition]
) -> list[ScoreComponent]:
    out: list[ScoreComponent] = []
    for c in result.components:
        d = defs.get(c.metric)
        scored = c.normalized_value is not None and result.score is not None
        out.append(
            ScoreComponent(
                metric=c.metric,
                display_name=d.display_name if d else None,
                raw_value=c.raw_value,
                normalized_value=c.normalized_value,
                weight=c.weight,
                effective_weight=c.effective_weight,
                contribution=c.contribution if scored else None,
                confidence=c.confidence,
            )
        )
    return out


def highlights(
    components: list[ScoreComponent], defs: Mapping[str, MetricDefinition]
) -> tuple[list[MetricHighlight], list[MetricHighlight]]:
    """Top strengths (highest normalized) and risks (lowest), disjoint, deterministic."""
    avail = sorted(
        (c for c in components if c.normalized_value is not None),
        key=lambda c: (-(c.normalized_value or 0.0), c.metric),
    )

    def hl(c: ScoreComponent) -> MetricHighlight:
        d = defs.get(c.metric)
        assert c.normalized_value is not None
        return MetricHighlight(
            metric=c.metric,
            display_name=c.display_name,
            raw_value=c.raw_value,
            normalized_value=c.normalized_value,
            unit=d.unit if d else None,
        )

    strengths = avail[:HIGHLIGHT_COUNT]
    taken = {c.metric for c in strengths}
    risks = [c for c in reversed(avail) if c.metric not in taken][:HIGHLIGHT_COUNT]
    return [hl(c) for c in strengths], [hl(c) for c in risks]


def peer_outliers(
    evals: list[Evaluated], metric_keys: Collection[str]
) -> dict[str, list[PeerOutlier]]:
    """DQ-006 over the compared set (area id string -> findings). Needs >= 3 areas with data."""
    out: dict[str, list[PeerOutlier]] = {}
    for key in sorted(metric_keys):
        values: dict[str, float | None] = {
            str(e.area.id): (e.metrics[key].raw_value if key in e.metrics else None)
            for e in evals
            if e.run is not None
        }
        for f in peer_outlier_findings(values, key):
            out.setdefault(str(f.metadata["area"]), []).append(
                PeerOutlier(
                    severity=f.severity,
                    metric=key,
                    message=f.message,
                    value=f.metadata["value"],
                    median=f.metadata["median"],
                    mad=f.metadata["mad"],
                )
            )
    return out


def definitions(session: Session) -> dict[str, MetricDefinition]:
    return metric_definitions.get_all(session)
