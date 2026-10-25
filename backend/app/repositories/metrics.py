"""Metric reads. Every query is scoped by analysis_run_id; there is no cross-run read."""

import uuid

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
