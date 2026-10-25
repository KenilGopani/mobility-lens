from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ScoringModel


def get_default(session: Session) -> ScoringModel | None:
    return session.scalars(select(ScoringModel).where(ScoringModel.is_default)).one_or_none()


def get_by_name_version(session: Session, name: str, version: str) -> ScoringModel | None:
    return session.scalars(
        select(ScoringModel).where(ScoringModel.name == name, ScoringModel.version == version)
    ).one_or_none()


def list_all(session: Session) -> list[ScoringModel]:
    return list(
        session.scalars(select(ScoringModel).order_by(ScoringModel.name, ScoringModel.version))
    )


def create(
    session: Session,
    *,
    name: str,
    version: str,
    weights: dict[str, Any],
    normalization_version: str,
    is_default: bool = False,
) -> ScoringModel:
    if is_default:
        clear_default(session)
    model = ScoringModel(
        name=name,
        version=version,
        weights=weights,
        normalization_version=normalization_version,
        is_default=is_default,
    )
    session.add(model)
    session.flush()
    return model


def clear_default(session: Session) -> None:
    session.execute(update(ScoringModel).where(ScoringModel.is_default).values(is_default=False))


def set_default(session: Session, model: ScoringModel) -> None:
    """Make `model` the single default (previous default is cleared first)."""
    clear_default(session)
    model.is_default = True
    session.flush()
