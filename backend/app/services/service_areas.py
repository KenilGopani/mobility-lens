"""Service-area read use cases (list, detail, summary, metrics, quality, cells)."""

import json
import uuid
from collections import Counter

from sqlalchemy.orm import Session

from app.models import AnalysisRun, ServiceArea
from app.repositories import analysis_runs, metrics, quality_findings, service_areas
from app.repositories.inputs import BBox
from app.schemas.api import (
    AreaMetricsResponse,
    CellFeature,
    CellProperties,
    CellsResponse,
    Completeness,
    Finding,
    MetricCompleteness,
    MetricHighlight,
    MetricValue,
    QualityResponse,
    ScoreComponent,
    ServiceAreaDetail,
    ServiceAreaListItem,
    ServiceAreaPage,
    ServiceAreaSummary,
    SeverityCounts,
)
from app.scoring.engine import MetricInput, score_area
from app.services import evaluation as ev
from app.services.errors import InvalidRequestError, NotFoundError

OVERALL_SCORE = "overall_score"
LOW_CONFIDENCE_THRESHOLD = 0.5


def _area_or_404(session: Session, area_id: uuid.UUID) -> ServiceArea:
    area = service_areas.get_light(session, area_id)
    if area is None:
        raise NotFoundError("Service area not found", {"service_area_id": str(area_id)})
    return area


def _run_or_404(session: Session, area: ServiceArea, run_id: uuid.UUID | None) -> AnalysisRun:
    """The requested run (must belong to the area) or the area's latest succeeded run."""
    if run_id is not None:
        run = analysis_runs.get(session, run_id)
        if run is None or run.service_area_id != area.id:
            raise NotFoundError(
                "Analysis run not found for this service area", {"analysis_run_id": str(run_id)}
            )
        return run
    latest = analysis_runs.latest_succeeded_for_area(session, area.id)
    if latest is None:
        raise NotFoundError(
            "No successful analysis run for this service area",
            {"service_area_id": str(area.id)},
        )
    return latest


def _evaluate_all(session: Session) -> list[ev.Evaluated]:
    model = ev.default_model(session)
    areas = service_areas.list_light(session)
    if model is None:
        return [ev.Evaluated(a, None, {}, None) for a in areas]
    weights = {k: float(v) for k, v in model.weights.items()}
    return ev.evaluate_areas(session, areas, weights)


def list_areas(session: Session, limit: int, offset: int) -> ServiceAreaPage:
    evals = _evaluate_all(session)
    items = [
        ServiceAreaListItem(
            id=e.area.id,
            name=e.area.name,
            slug=e.area.slug,
            source=e.area.source,
            score=e.result.score if e.result else None,
            confidence=e.result.confidence if e.result else None,
            rank=e.rank,
            analysis_run_id=e.run.id if e.run else None,
            last_run_at=(e.run.completed_at or e.run.started_at) if e.run else None,
        )
        for e in evals[offset : offset + limit]
    ]
    return ServiceAreaPage(items=items, total=len(evals), limit=limit, offset=offset)


def get_detail(session: Session, area_id: uuid.UUID) -> ServiceAreaDetail:
    area = _area_or_404(session, area_id)
    boundary, bbox = service_areas.boundary_geojson(session, area.id)
    return ServiceAreaDetail(
        id=area.id,
        name=area.name,
        slug=area.slug,
        source=area.source,
        created_at=area.created_at,
        updated_at=area.updated_at,
        bbox=bbox,
        boundary=boundary,
    )


def _counts(findings: list[Finding]) -> SeverityCounts:
    c = Counter(f.severity.value for f in findings)
    return SeverityCounts(info=c["info"], warning=c["warning"], critical=c["critical"])


def _findings(session: Session, run_id: uuid.UUID) -> list[Finding]:
    return [
        Finding(
            rule_key=f.rule_key,
            severity=f.severity,
            message=f.message,
            affected_fraction=f.affected_fraction,
            metadata=f.metadata_,
        )
        for f in quality_findings.list_for_run(session, run_id)
    ]


def get_summary(session: Session, area_id: uuid.UUID) -> ServiceAreaSummary:
    area = _area_or_404(session, area_id)
    model = ev.default_model(session)
    evals = _evaluate_all(session)
    mine = next(e for e in evals if e.area.id == area.id)
    ranked = sum(1 for e in evals if e.rank is not None)
    defs = ev.definitions(session)
    warnings: list[str] = []
    if model is None:
        warnings.append("no_default_scoring_model")
    if mine.run is None:
        warnings.append(ev.NO_SUCCESSFUL_RUN)
        return ServiceAreaSummary(
            id=area.id,
            name=area.name,
            slug=area.slug,
            scoring_model=ev.model_ref(model) if model else None,
            ranked_areas=ranked,
            warnings=warnings,
            finding_counts=SeverityCounts(),
        )
    findings = _findings(session, mine.run.id)
    components: list[ScoreComponent] = []
    strengths: list[MetricHighlight] = []
    risks: list[MetricHighlight] = []
    if mine.result is not None:
        components = ev.components_out(mine.result, defs)
        strengths, risks = ev.highlights(components, defs)
        warnings.extend(mine.result.warnings)
    return ServiceAreaSummary(
        id=area.id,
        name=area.name,
        slug=area.slug,
        scoring_model=ev.model_ref(model) if model else None,
        score=mine.result.score if mine.result else None,
        confidence=mine.result.confidence if mine.result else None,
        rank=mine.rank,
        ranked_areas=ranked,
        components=components,
        strengths=strengths,
        risks=risks,
        warnings=warnings,
        finding_counts=_counts(findings),
        run=ev.run_ref(mine.run),
    )


def get_metrics(
    session: Session, area_id: uuid.UUID, analysis_run_id: uuid.UUID | None
) -> AreaMetricsResponse:
    area = _area_or_404(session, area_id)
    run = _run_or_404(session, area, analysis_run_id)
    defs = ev.definitions(session)
    rows = metrics.area_metrics_for_runs(session, [run.id]).get(run.id, {})
    values = []
    for key in sorted(defs):
        d = defs[key]
        m = rows.get(key)
        values.append(
            MetricValue(
                key=key,
                display_name=d.display_name,
                description=d.description,
                unit=d.unit,
                higher_is_better=d.higher_is_better,
                normalization_method=d.normalization_method,
                ref_min=d.ref_min,
                ref_max=d.ref_max,
                version=d.version,
                raw_value=m.raw_value if m else None,
                normalized_value=m.normalized_value if m else None,
                confidence=m.confidence if m else None,
            )
        )
    return AreaMetricsResponse(
        service_area_id=area.id,
        run=ev.run_ref(run),
        analyzed_at=run.completed_at,
        source=run.source_metadata,
        metrics=values,
    )


def get_quality(
    session: Session, area_id: uuid.UUID, analysis_run_id: uuid.UUID | None
) -> QualityResponse:
    area = _area_or_404(session, area_id)
    run = _run_or_404(session, area, analysis_run_id)
    defs = ev.definitions(session)
    findings = _findings(session, run.id)
    cells, present, low = metrics.completeness_stats(session, run.id, LOW_CONFIDENCE_THRESHOLD)
    per_metric = [
        MetricCompleteness(
            metric=key,
            null_cells=cells - present.get(key, 0),
            null_share=(cells - present.get(key, 0)) / cells if cells else None,
        )
        for key in sorted(defs)
    ]
    return QualityResponse(
        service_area_id=area.id,
        run=ev.run_ref(run),
        analyzed_at=run.completed_at,
        source=run.source_metadata,
        findings=findings,
        finding_counts=_counts(findings),
        completeness=Completeness(
            cells_count=cells,
            low_confidence_threshold=LOW_CONFIDENCE_THRESHOLD,
            low_confidence_cells=low,
            low_confidence_share=low / cells if cells else None,
            metrics=per_metric,
        ),
    )


def get_cells(
    session: Session,
    area_id: uuid.UUID,
    *,
    metric: str,
    analysis_run_id: uuid.UUID | None,
    bbox: BBox | None,
    limit: int,
) -> CellsResponse:
    area = _area_or_404(session, area_id)
    allowed = {OVERALL_SCORE, *ev.definitions(session)}
    if metric not in allowed:
        raise InvalidRequestError(
            f"Unknown metric {metric!r}", {"metric": metric, "allowed": sorted(allowed)}
        )
    run = _run_or_404(session, area, analysis_run_id)
    weights: dict[str, float] | None = None
    if metric == OVERALL_SCORE:
        model = ev.default_model(session)
        if model is None:
            raise NotFoundError("No default scoring model configured")
        weights = {k: float(v) for k, v in model.weights.items()}

    rows = metrics.list_run_cells(session, run.id, bbox, limit + 1)
    truncated = len(rows) > limit
    rows = rows[:limit]
    by_cell = metrics.cell_metrics_for_cells(session, run.id, [r[0] for r in rows])

    features: list[CellFeature] = []
    for h3_index, overlap, geom in rows:
        cm = by_cell.get(h3_index, {})
        props = CellProperties(h3_index=h3_index, overlap_ratio=overlap)
        if weights is not None:
            result = score_area(
                {
                    k: MetricInput(m.normalized_value, m.confidence, m.raw_value)
                    for k, m in cm.items()
                },
                weights,
            )
            props.score = result.score
            props.confidence = result.confidence if result.score is not None else None
        elif metric in cm:
            m = cm[metric]
            props.raw_value, props.normalized_value, props.confidence = (
                m.raw_value,
                m.normalized_value,
                m.confidence,
            )
        features.append(CellFeature(geometry=json.loads(geom), properties=props))
    return CellsResponse(
        metric=metric,
        analysis_run_id=run.id,
        limit=limit,
        truncated=truncated,
        features=features,
    )
