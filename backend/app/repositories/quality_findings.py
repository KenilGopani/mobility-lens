import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataQualityFinding


def add(
    session: Session,
    *,
    analysis_run_id: uuid.UUID,
    rule_key: str,
    severity: str,
    message: str,
    affected_fraction: float | None = None,
    metadata: dict[str, object] | None = None,
) -> DataQualityFinding:
    finding = DataQualityFinding(
        analysis_run_id=analysis_run_id,
        rule_key=rule_key,
        severity=severity,
        message=message,
        affected_fraction=affected_fraction,
        metadata_=metadata,
    )
    session.add(finding)
    session.flush()
    return finding


def list_for_run(session: Session, analysis_run_id: uuid.UUID) -> list[DataQualityFinding]:
    stmt = (
        select(DataQualityFinding)
        .where(DataQualityFinding.analysis_run_id == analysis_run_id)
        .order_by(DataQualityFinding.rule_key, DataQualityFinding.message)
    )
    return list(session.scalars(stmt))
