from fastapi import APIRouter

from app.api.v1 import analysis_runs, comparisons, operations, scoring_models, service_areas

router = APIRouter(prefix="/api/v1")
router.include_router(service_areas.router)
router.include_router(comparisons.router)
router.include_router(analysis_runs.router)
router.include_router(scoring_models.router)
router.include_router(operations.router)
