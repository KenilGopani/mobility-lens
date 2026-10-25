"""Metric reads. Every query is scoped by analysis_run_id; there is no cross-run read."""

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRunCell, AreaMetric, CellMetric, H3Cell
from app.repositories.inputs import BBox


def list_cell_metrics(
    session: Session, analysis_run_id: uuid.UUID, metric_key: str | None = None
) -> list[CellMetric]:
    stmt = select(CellMetric).where(CellMetric.analysis_run_id == analysis_run_id)
    if metric_key is not None:
        stmt = stmt.where(CellMetric.metric_key == metric_key)
    return list(session.scalars(stmt.order_by(CellMetric.h3_index, CellMetric.metric_key)))


def list_area_metrics(session: Session, analysis_run_id: uuid.UUID) -> list[AreaMetric]:
    stmt = (
        select(AreaMetric)
        .where(AreaMetric.analysis_run_id == analysis_run_id)
        .order_by(AreaMetric.metric_key)
    )
    return list(session.scalars(stmt))


def cells_in_bbox(session: Session, analysis_run_id: uuid.UUID, bbox: BBox) -> list[H3Cell]:
    """Cells of this run whose boundary intersects the bbox (GiST-assisted ST_Intersects)."""
    envelope = func.ST_MakeEnvelope(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat, 4326)
    stmt = (
        select(H3Cell)
        .join(AnalysisRunCell, AnalysisRunCell.h3_index == H3Cell.h3_index)
        .where(
            AnalysisRunCell.analysis_run_id == analysis_run_id,
            func.ST_Intersects(H3Cell.boundary, envelope),
        )
        .order_by(H3Cell.h3_index)
    )
    return list(session.scalars(stmt))


def area_metrics_for_runs(
    session: Session, run_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, AreaMetric]]:
    """Area metrics of several runs in one query: run id -> metric key -> row."""
    out: dict[uuid.UUID, dict[str, AreaMetric]] = defaultdict(dict)
    if not run_ids:
        return out
    for m in session.scalars(select(AreaMetric).where(AreaMetric.analysis_run_id.in_(run_ids))):
        out[m.analysis_run_id][m.metric_key] = m
    return out


def list_run_cells(
    session: Session, analysis_run_id: uuid.UUID, bbox: BBox | None, limit: int
) -> list[tuple[str, float, str]]:
    """(h3_index, overlap_ratio, boundary GeoJSON text) ordered by h3_index, at most `limit`."""
    stmt = (
        select(
            AnalysisRunCell.h3_index,
            AnalysisRunCell.overlap_ratio,
            func.ST_AsGeoJSON(H3Cell.boundary, 6),
        )
        .join(H3Cell, H3Cell.h3_index == AnalysisRunCell.h3_index)
        .where(AnalysisRunCell.analysis_run_id == analysis_run_id)
    )
    if bbox is not None:
        envelope = func.ST_MakeEnvelope(
            bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat, 4326
        )
        stmt = stmt.where(func.ST_Intersects(H3Cell.boundary, envelope))
    stmt = stmt.order_by(AnalysisRunCell.h3_index).limit(limit)
    return [(r[0], r[1], r[2]) for r in session.execute(stmt)]


def cell_metrics_for_cells(
    session: Session, analysis_run_id: uuid.UUID, h3_indexes: list[str]
) -> dict[str, dict[str, CellMetric]]:
    """Cell metrics for the given cells in one query: h3_index -> metric key -> row."""
    out: dict[str, dict[str, CellMetric]] = defaultdict(dict)
    if not h3_indexes:
        return out
    stmt = select(CellMetric).where(
        CellMetric.analysis_run_id == analysis_run_id, CellMetric.h3_index.in_(h3_indexes)
    )
    for m in session.scalars(stmt):
        out[m.h3_index][m.metric_key] = m
    return out


def completeness_stats(
    session: Session, analysis_run_id: uuid.UUID, low_confidence_below: float
) -> tuple[int, dict[str, int], int]:
    """(cells in run, metric key -> cells with a non-null raw value, cells with any metric
    confidence below the threshold)."""
    cells = (
        session.scalar(
            select(func.count())
            .select_from(AnalysisRunCell)
            .where(AnalysisRunCell.analysis_run_id == analysis_run_id)
        )
        or 0
    )
    present = {
        key: int(n)
        for key, n in session.execute(
            select(CellMetric.metric_key, func.count())
            .where(CellMetric.analysis_run_id == analysis_run_id, CellMetric.raw_value.is_not(None))
            .group_by(CellMetric.metric_key)
        )
    }
    low = (
        session.scalar(
            select(func.count(func.distinct(CellMetric.h3_index))).where(
                CellMetric.analysis_run_id == analysis_run_id,
                CellMetric.confidence < low_confidence_below,
            )
        )
        or 0
    )
    return cells, present, int(low)
