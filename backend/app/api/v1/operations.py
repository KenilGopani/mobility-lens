import uuid

from fastapi import APIRouter

from app.api.v1.deps import ERROR_RESPONSES, Limit, Offset, SessionDep
from app.schemas.operations import OperationsSummary, SimulationPage
from app.services import operations as svc

router = APIRouter(
    prefix="/service-areas", tags=["synthetic operations"], responses=ERROR_RESPONSES
)


@router.get("/{service_area_id}/simulations", response_model=SimulationPage)
def list_simulations(
    service_area_id: uuid.UUID, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> SimulationPage:
    return svc.list_runs(session, service_area_id, limit, offset)


@router.get("/{service_area_id}/operations", response_model=OperationsSummary)
def operations_summary(
    service_area_id: uuid.UUID, session: SessionDep, simulation_run_id: uuid.UUID | None = None
) -> OperationsSummary:
    return svc.summary(session, service_area_id, simulation_run_id)
