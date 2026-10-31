import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.orm import Session

from app.models import AnalysisRun, AnalysisRunCell, AreaMetric, CellMetric, H3Cell
from app.repositories.inputs import AreaMetricInput, CellMetricInput, RunCellInput
from app.schemas import RunStatus


def create_run(
    session: Session,
    *,
    service_area_id: uuid.UUID,
    pipeline_version: str,
    parameters: dict[str, Any],
    source_metadata: dict[str, Any] | None = None,
    started_at: datetime | None = None,
) -> AnalysisRun:
    run = AnalysisRun(
        service_area_id=service_area_id,
        pipeline_version=pipeline_version,
        parameters=parameters,
        status=RunStatus.RUNNING.value,
        started_at=started_at or datetime.now(UTC),
        source_metadata=source_metadata or {},
    )
    session.add(run)
    session.flush()
    return run


def get(session: Session, run_id: uuid.UUID) -> AnalysisRun | None:
    return session.get(AnalysisRun, run_id)


def latest_succeeded_for_area(session: Session, service_area_id: uuid.UUID) -> AnalysisRun | None:
    stmt = (
        select(AnalysisRun)
        .where(
            AnalysisRun.service_area_id == service_area_id,
            AnalysisRun.status == RunStatus.SUCCEEDED.value,
        )
        .order_by(
            AnalysisRun.completed_at.desc().nulls_last(),
            AnalysisRun.started_at.desc(),
            AnalysisRun.id,
        )
        .limit(1)
    )
    return session.scalars(stmt).one_or_none()


def mark_failed(session: Session, run: AnalysisRun, error_message: str) -> None:
    run.status = RunStatus.FAILED.value
    run.error_message = error_message
    run.completed_at = datetime.now(UTC)
    session.flush()


def persist_results(
    session: Session,
    run: AnalysisRun,
    *,
    cells: list[RunCellInput],
    cell_metrics: list[CellMetricInput],
    area_metrics: list[AreaMetricInput],
    source_metadata: dict[str, Any] | None = None,
) -> None:
    """Write all data tables for a run atomically and mark it succeeded.

    Runs in a SAVEPOINT: if anything fails, none of the run's data rows are written and the
    exception propagates (the caller can then record the failure with `mark_failed`).
    """
    with session.begin_nested():
        for rc in cells:
            c = rc.cell
            session.execute(
                insert(H3Cell)
                .values(
                    h3_index=c.h3_index,
                    resolution=c.resolution,
                    boundary=f"SRID=4326;{c.boundary_wkt}",
                    centroid=f"SRID=4326;{c.centroid_wkt}",
                )
                .on_conflict_do_nothing(index_elements=["h3_index"])
            )
        session.add_all(
            AnalysisRunCell(
                analysis_run_id=run.id, h3_index=rc.cell.h3_index, overlap_ratio=rc.overlap_ratio
            )
            for rc in cells
        )
        session.flush()
        session.add_all(
            CellMetric(
                analysis_run_id=run.id,
                h3_index=m.h3_index,
                metric_key=m.metric_key,
                raw_value=m.raw_value,
                normalized_value=m.normalized_value,
                confidence=m.confidence,
                metadata_=m.metadata,
            )
            for m in cell_metrics
        )
        session.add_all(
            AreaMetric(
                analysis_run_id=run.id,
                metric_key=a.metric_key,
                raw_value=a.raw_value,
                normalized_value=a.normalized_value,
                confidence=a.confidence,
            )
            for a in area_metrics
        )
        run.status = RunStatus.SUCCEEDED.value
        run.completed_at = datetime.now(UTC)
        if source_metadata is not None:
            run.source_metadata = source_metadata
        session.flush()


def latest_succeeded_for_areas(
    session: Session, service_area_ids: list[uuid.UUID]
) -> dict[uuid.UUID, AnalysisRun]:
    """Latest succeeded run per area in one query (same ordering as the single-area lookup)."""
    stmt = (
        select(AnalysisRun)
        .where(
            AnalysisRun.service_area_id.in_(service_area_ids),
            AnalysisRun.status == RunStatus.SUCCEEDED.value,
        )
        .ext(distinct_on(AnalysisRun.service_area_id))
        .order_by(
            AnalysisRun.service_area_id,
            AnalysisRun.completed_at.desc().nulls_last(),
            AnalysisRun.started_at.desc(),
            AnalysisRun.id,
        )
    )
    return {r.service_area_id: r for r in session.scalars(stmt)}


def list_runs(
    session: Session,
    *,
    service_area_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AnalysisRun], int]:
    """Runs newest first (started_at desc, id), plus the total matching count."""
    conds = []
    if service_area_id is not None:
        conds.append(AnalysisRun.service_area_id == service_area_id)
    if status is not None:
        conds.append(AnalysisRun.status == status)
    total = session.scalar(select(func.count()).select_from(AnalysisRun).where(*conds)) or 0
    stmt = (
        select(AnalysisRun)
        .where(*conds)
        .order_by(AnalysisRun.started_at.desc(), AnalysisRun.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt)), total


def stale_running(session: Session, before: datetime, *, lock: bool = False) -> list[AnalysisRun]:
    stmt = (
        select(AnalysisRun)
        .where(
            AnalysisRun.status == RunStatus.RUNNING.value,
            AnalysisRun.started_at < before,
        )
        .order_by(AnalysisRun.started_at, AnalysisRun.id)
    )
    if lock:
        stmt = stmt.with_for_update(skip_locked=True)
    return list(session.scalars(stmt))
