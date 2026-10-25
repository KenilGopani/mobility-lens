"""Orchestrates the analysis of one service area (docs/architecture.md, pipeline stages).

Stages: boundary -> network -> cells -> metrics -> normalize (hook) -> persist -> quality (hook).
Normalization and data-quality evaluation are injected callables defaulting to no-ops; the CLI
wires the real ones once app/scoring and app/quality exist.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import h3
from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AnalysisRun
from app.repositories import analysis_runs, quality_findings, service_areas
from app.repositories.inputs import (
    AreaMetricInput,
    CellMetricInput,
    H3CellInput,
    RunCellInput,
)
from pipelines.metrics import (
    METRIC_KEYS,
    compute_area_metrics,
    compute_cell_metrics,
    prepare_network,
)
from pipelines.osm import NetworkSnapshot, fetch_drive_network
from pipelines.spatial import (
    area_km2,
    cell_polygon,
    cell_regions,
    cover_cells,
    estimate_utm_crs,
    project_geometry,
    validate_boundary,
)
from pipelines.stages import get_run_logger, stage

PIPELINE_VERSION = "0.1.0"
NETWORK_TYPE = "drive"
MAX_ERROR_LENGTH = 2000

NetworkProvider = Callable[[BaseGeometry, str], NetworkSnapshot]


class AreaNotFoundError(LookupError):
    """No service area with the requested slug (no run is created)."""


@dataclass(frozen=True)
class FindingInput:
    """A data-quality finding to persist (mirrors quality_findings.add)."""

    rule_key: str
    severity: str
    message: str
    affected_fraction: float | None = None
    metadata: dict[str, object] | None = None


@dataclass
class AnalysisContext:
    """Everything a quality evaluator may inspect (read-only by convention)."""

    analysis_run_id: uuid.UUID
    service_area_id: uuid.UUID
    parameters: dict[str, Any]
    source_metadata: dict[str, Any]
    area_km2: float
    node_count: int
    edge_count: int
    cells: list[RunCellInput]
    cell_metrics: list[CellMetricInput]
    area_metrics: list[AreaMetricInput]


# HOOKS. Defaults are explicit no-ops: normalized_value stays None and no findings are written.
Normalizer = Callable[
    [list[CellMetricInput], list[AreaMetricInput]],
    tuple[list[CellMetricInput], list[AreaMetricInput]],
]
QualityEvaluator = Callable[[AnalysisContext], list[FindingInput]]


def no_op_normalizer(
    cell_metrics: list[CellMetricInput], area_metrics: list[AreaMetricInput]
) -> tuple[list[CellMetricInput], list[AreaMetricInput]]:
    return cell_metrics, area_metrics


def no_op_quality_evaluator(context: AnalysisContext) -> list[FindingInput]:
    return []


def default_network_provider(polygon: BaseGeometry, query: str) -> NetworkSnapshot:
    return fetch_drive_network(polygon, query=query)


@dataclass
class AnalysisSummary:
    analysis_run_id: uuid.UUID
    service_area_id: uuid.UUID
    cell_count: int
    area_km2: float
    node_count: int
    edge_count: int
    area_metrics: dict[str, float | None]
    findings: int
    source_metadata: dict[str, Any] = field(default_factory=dict)


def _cell_input(h3_index: str, resolution: int) -> H3CellInput:
    lat, lng = h3.cell_to_latlng(h3_index)
    return H3CellInput(
        h3_index=h3_index,
        resolution=resolution,
        boundary_wkt=cell_polygon(h3_index).wkt,
        centroid_wkt=Point(lng, lat).wkt,
    )


def analyze_area(
    session: Session,
    slug: str,
    *,
    network_provider: NetworkProvider = default_network_provider,
    h3_resolution: int | None = None,
    normalizer: Normalizer = no_op_normalizer,
    quality_evaluator: QualityEvaluator = no_op_quality_evaluator,
) -> AnalysisSummary:
    """Run the pipeline for `slug`, creating a new analysis run every time.

    The run row is committed up front (status running) so a failure can be recorded after the
    data transaction is rolled back. On any exception the run is marked failed with
    `error_message` and the exception is re-raised.
    """
    area = service_areas.get_by_slug(session, slug)
    if area is None:
        raise AreaNotFoundError(f"service area {slug!r} not found (run seed-service-areas)")
    resolution = h3_resolution if h3_resolution is not None else get_settings().h3_resolution
    parameters: dict[str, Any] = {
        "h3_resolution": resolution,
        "network_type": NETWORK_TYPE,
        "simplify": True,
    }
    run = analysis_runs.create_run(
        session,
        service_area_id=area.id,
        pipeline_version=PIPELINE_VERSION,
        parameters=parameters,
    )
    session.commit()
    run_id, area_id = run.id, area.id
    log = get_run_logger(run_id, area_id)
    log.info("analysis_started", slug=slug, h3_resolution=resolution)
    captured_metadata: dict[str, Any] = {}
    try:
        summary = _run_stages(
            session,
            run,
            area_name=area.name,
            boundary_geom=to_shape(area.boundary),
            parameters=parameters,
            captured_metadata=captured_metadata,
            log=log,
            network_provider=network_provider,
            normalizer=normalizer,
            quality_evaluator=quality_evaluator,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        failed = analysis_runs.get(session, run_id)
        if failed is not None:
            if captured_metadata:
                failed.source_metadata = captured_metadata
            analysis_runs.mark_failed(
                session, failed, f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
            )
            session.commit()
        log.error("analysis_failed", error=f"{type(exc).__name__}: {exc}")
        raise
    log.info("analysis_succeeded", cell_count=summary.cell_count, area_km2=summary.area_km2)
    return summary


def _run_stages(
    session: Session,
    run: AnalysisRun,
    *,
    area_name: str,
    boundary_geom: BaseGeometry,
    parameters: dict[str, Any],
    captured_metadata: dict[str, Any],
    log: Any,
    network_provider: NetworkProvider,
    normalizer: Normalizer,
    quality_evaluator: QualityEvaluator,
) -> AnalysisSummary:
    resolution = int(parameters["h3_resolution"])

    with stage(log, "boundary") as counts:
        repaired = validate_boundary(boundary_geom)
        boundary = repaired.geometry
        crs = estimate_utm_crs(boundary)
        boundary_p = project_geometry(boundary, crs)
        total_km2 = area_km2(boundary, crs)
        parameters = {
            **parameters,
            "utm_crs": crs.to_string(),
            "boundary_repaired": repaired.repaired,
        }
        run.parameters = parameters
        counts.update(area_km2=round(total_km2, 4), repaired=repaired.repaired)

    with stage(log, "network") as counts:
        snapshot = network_provider(boundary, area_name)
        captured_metadata.update(snapshot.source_metadata)
        net = prepare_network(snapshot.graph, crs)
        counts.update(nodes=len(net.nodes), edges=len(net.edges))

    with stage(log, "cells") as counts:
        regions = cell_regions(boundary, cover_cells(boundary, resolution), crs)
        kept = {c: v for c, v in regions.items() if v[1] > 0.0}
        cells = [RunCellInput(_cell_input(c, resolution), ratio) for c, (_, ratio) in kept.items()]
        counts.update(cells=len(cells))

    with stage(log, "metrics") as counts:
        cell_metrics: list[CellMetricInput] = []
        for c, (region, ratio) in kept.items():
            m = compute_cell_metrics(net, region, overlap_ratio=ratio)
            meta = {
                "node_count": m.node_count,
                "edge_count": m.edge_count,
                "area_km2": round(m.area_km2, 6),
            }
            cell_metrics.extend(
                CellMetricInput(c, k, m.raw[k], None, m.confidence[k], meta) for k in METRIC_KEYS
            )
        am = compute_area_metrics(net, boundary_p)
        area_metrics = [AreaMetricInput(k, am.raw[k], None, am.confidence[k]) for k in METRIC_KEYS]
        counts.update(cell_metrics=len(cell_metrics), area_metrics=len(area_metrics))

    with stage(log, "normalize") as counts:
        cell_metrics, area_metrics = normalizer(cell_metrics, area_metrics)
        counts.update(
            normalized=sum(m.normalized_value is not None for m in cell_metrics)
            + sum(m.normalized_value is not None for m in area_metrics)
        )

    source_metadata = {**snapshot.source_metadata, "boundary_area_km2": round(total_km2, 6)}
    with stage(log, "persist") as counts:
        analysis_runs.persist_results(
            session,
            run,
            cells=cells,
            cell_metrics=cell_metrics,
            area_metrics=area_metrics,
            source_metadata=source_metadata,
        )
        counts.update(cells=len(cells), cell_metrics=len(cell_metrics))

    with stage(log, "quality") as counts:
        context = AnalysisContext(
            analysis_run_id=run.id,
            service_area_id=run.service_area_id,
            parameters=parameters,
            source_metadata=source_metadata,
            area_km2=total_km2,
            node_count=am.node_count,
            edge_count=am.edge_count,
            cells=cells,
            cell_metrics=cell_metrics,
            area_metrics=area_metrics,
        )
        findings = quality_evaluator(context)
        for f in findings:
            quality_findings.add(
                session,
                analysis_run_id=run.id,
                rule_key=f.rule_key,
                severity=f.severity,
                message=f.message,
                affected_fraction=f.affected_fraction,
                metadata=f.metadata,
            )
        counts.update(findings=len(findings))

    return AnalysisSummary(
        analysis_run_id=run.id,
        service_area_id=run.service_area_id,
        cell_count=len(cells),
        area_km2=total_km2,
        node_count=am.node_count,
        edge_count=am.edge_count,
        area_metrics={m.metric_key: m.raw_value for m in area_metrics},
        findings=len(findings),
        source_metadata=source_metadata,
    )
