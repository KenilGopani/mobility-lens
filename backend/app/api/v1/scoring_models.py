from fastapi import APIRouter

from app.api.v1.deps import SessionDep
from app.schemas.api import ScoringModelList
from app.services import runs as svc

router = APIRouter(prefix="/scoring-models", tags=["scoring"])


@router.get("", response_model=ScoringModelList, summary="Scoring models (default flagged)")
def list_scoring_models(session: SessionDep) -> ScoringModelList:
    return svc.list_models(session)
