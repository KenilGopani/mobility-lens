import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import ERROR_RESPONSES, Limit, Offset, SessionDep
from app.repositories.inputs import BBox
from app.schemas.api import (
    AreaMetricsResponse,
    CellsResponse,
    QualityResponse,
    ServiceAreaDetail,
    ServiceAreaPage,
    ServiceAreaSummary,
)
from app.services import service_areas as svc
from app.services.errors import InvalidRequestError

router = APIRouter(prefix="/service-areas", tags=["service-areas"], responses=ERROR_RESPONSES)

RunId = Annotated[uuid.UUID | None, Query(description="Defaults to the latest succeeded run")]


def parse_bbox(
    bbox: Annotated[
        str | None, Query(description="minLon,minLat,maxLon,maxLat (EPSG:4326)")
    ] = None,
) -> BBox | None:
    if bbox is None:
        return None
    try:
        parts = [float(p) for p in bbox.split(",")]
    except ValueError:
        parts = []
    if len(parts) != 4 or not all(-1e9 < p < 1e9 for p in parts):
        raise InvalidRequestError("bbox must be minLon,minLat,maxLon,maxLat", {"bbox": bbox})
    min_lon, min_lat, max_lon, max_lat = parts
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise InvalidRequestError(
            "bbox out of range: lon in [-180,180], lat in [-90,90], min < max", {"bbox": bbox}
        )
    return BBox(min_lon, min_lat, max_lon, max_lat)


@router.get("", response_model=ServiceAreaPage, summary="List service areas")
def list_service_areas(
    session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> ServiceAreaPage:
    return svc.list_areas(session, limit, offset)


@router.get("/{service_area_id}", response_model=ServiceAreaDetail, summary="Area detail")
def get_service_area(service_area_id: uuid.UUID, session: SessionDep) -> ServiceAreaDetail:
    return svc.get_detail(session, service_area_id)


@router.get("/{service_area_id}/summary", response_model=ServiceAreaSummary, summary="Area summary")
def get_summary(service_area_id: uuid.UUID, session: SessionDep) -> ServiceAreaSummary:
    return svc.get_summary(session, service_area_id)


@router.get(
    "/{service_area_id}/metrics", response_model=AreaMetricsResponse, summary="Area metrics"
)
def get_metrics(
    service_area_id: uuid.UUID, session: SessionDep, analysis_run_id: RunId = None
) -> AreaMetricsResponse:
    return svc.get_metrics(session, service_area_id, analysis_run_id)


@router.get("/{service_area_id}/quality", response_model=QualityResponse, summary="Data quality")
def get_quality(
    service_area_id: uuid.UUID, session: SessionDep, analysis_run_id: RunId = None
) -> QualityResponse:
    return svc.get_quality(session, service_area_id, analysis_run_id)


@router.get("/{service_area_id}/cells", response_model=CellsResponse, summary="H3 cells (GeoJSON)")
def get_cells(
    service_area_id: uuid.UUID,
    session: SessionDep,
    bbox: Annotated[BBox | None, Depends(parse_bbox)],
    metric: Annotated[str, Query(description="A metric key or 'overall_score'")] = "overall_score",
    analysis_run_id: RunId = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 2000,
) -> CellsResponse:
    return svc.get_cells(
        session,
        service_area_id,
        metric=metric,
        analysis_run_id=analysis_run_id,
        bbox=bbox,
        limit=limit,
    )
