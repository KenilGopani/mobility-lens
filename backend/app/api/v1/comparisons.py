from fastapi import APIRouter

from app.api.v1.deps import ERROR_RESPONSES, SessionDep
from app.schemas.api import ComparisonRequest, ComparisonResponse, PreviewRequest, PreviewResponse
from app.services import comparisons as svc

router = APIRouter(tags=["scoring"], responses=ERROR_RESPONSES)


@router.post("/comparisons", response_model=ComparisonResponse, summary="Compare 2-3 areas")
def create_comparison(body: ComparisonRequest, session: SessionDep) -> ComparisonResponse:
    return svc.compare(session, body.service_area_ids, body.scoring_model_id)


@router.post(
    "/scoring/preview", response_model=PreviewResponse, summary="What-if scoring (not persisted)"
)
def preview_scoring(body: PreviewRequest, session: SessionDep) -> PreviewResponse:
    return svc.preview(session, body.service_area_ids, body.weights)
