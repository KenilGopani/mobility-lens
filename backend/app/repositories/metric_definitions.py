from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MetricDefinition


def get_all(session: Session) -> dict[str, MetricDefinition]:
    """All metric definitions keyed by metric key."""
    return {m.key: m for m in session.scalars(select(MetricDefinition))}
