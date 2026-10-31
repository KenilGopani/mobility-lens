"""Analysis-run and scoring-model read use cases."""

import uuid

from sqlalchemy.orm import Session

from app.repositories import analysis_runs, scoring_models
from app.schemas.api import AnalysisRunOut, AnalysisRunPage, ScoringModelList, ScoringModelOut
from app.schemas.domain import RunStatus
from app.services.errors import NotFoundError
from app.services.provenance import public_source


def _run_out(run: object) -> AnalysisRunOut:
    result = AnalysisRunOut.model_validate(run, from_attributes=True)
    return result.model_copy(update={"source_metadata": public_source(result.source_metadata)})


def list_runs(
    session: Session,
    *,
    service_area_id: uuid.UUID | None,
    status: RunStatus | None,
    limit: int,
    offset: int,
) -> AnalysisRunPage:
    rows, total = analysis_runs.list_runs(
        session,
        service_area_id=service_area_id,
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )
    return AnalysisRunPage(
        items=[_run_out(r) for r in rows], total=total, limit=limit, offset=offset
    )


def get_run(session: Session, run_id: uuid.UUID) -> AnalysisRunOut:
    run = analysis_runs.get(session, run_id)
    if run is None:
        raise NotFoundError("Analysis run not found", {"analysis_run_id": str(run_id)})
    return _run_out(run)


def list_models(session: Session) -> ScoringModelList:
    return ScoringModelList(
        items=[
            ScoringModelOut(
                id=m.id,
                name=m.name,
                version=m.version,
                weights={k: float(v) for k, v in m.weights.items()},
                normalization_version=m.normalization_version,
                is_default=m.is_default,
                created_at=m.created_at,
            )
            for m in scoring_models.list_all(session)
        ]
    )
