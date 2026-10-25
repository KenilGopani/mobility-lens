import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AreaScore


def add(
    session: Session,
    *,
    analysis_run_id: uuid.UUID,
    scoring_model_id: uuid.UUID,
    score: float | None,
    confidence: float,
    component_breakdown: dict[str, Any],
) -> AreaScore:
    row = AreaScore(
        analysis_run_id=analysis_run_id,
        scoring_model_id=scoring_model_id,
        score=score,
        confidence=confidence,
        component_breakdown=component_breakdown,
        calculated_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def list_for_run(session: Session, analysis_run_id: uuid.UUID) -> list[AreaScore]:
    stmt = select(AreaScore).where(AreaScore.analysis_run_id == analysis_run_id)
    return list(session.scalars(stmt))
