import uuid

from fastapi import APIRouter

from app.api.v1.deps import ERROR_RESPONSES, Limit, Offset, SessionDep
from app.schemas.api import AnalysisRunOut, AnalysisRunPage
from app.schemas.domain import RunStatus
from app.services import runs as svc

router = APIRouter(prefix="/analysis-runs", tags=["analysis-runs"], responses=ERROR_RESPONSES)


@router.get("", response_model=AnalysisRunPage, summary="List analysis runs (newest first)")
def list_analysis_runs(
    session: SessionDep,
    service_area_id: uuid.UUID | None = None,
    status: RunStatus | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> AnalysisRunPage:
    return svc.list_runs(
        session, service_area_id=service_area_id, status=status, limit=limit, offset=offset
    )


@router.get("/{analysis_run_id}", response_model=AnalysisRunOut, summary="Analysis run detail")
def get_analysis_run(analysis_run_id: uuid.UUID, session: SessionDep) -> AnalysisRunOut:
    return svc.get_run(session, analysis_run_id)
