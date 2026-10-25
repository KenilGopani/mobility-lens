import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ServiceArea


def _boundary_expr(geojson: Mapping[str, Any]) -> Any:
    """GeoJSON geometry -> MULTIPOLYGON in EPSG:4326, evaluated by PostGIS."""
    return func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(dict(geojson))), 4326))


def create(
    session: Session, *, name: str, slug: str, boundary_geojson: Mapping[str, Any], source: str
) -> ServiceArea:
    area = ServiceArea(
        name=name, slug=slug, source=source, boundary=_boundary_expr(boundary_geojson)
    )
    session.add(area)
    session.flush()
    return area


def upsert_by_slug(
    session: Session, *, name: str, slug: str, boundary_geojson: Mapping[str, Any], source: str
) -> tuple[ServiceArea, bool]:
    """Insert or update by slug. Returns (area, created)."""
    existing = get_by_slug(session, slug)
    if existing is None:
        return create(
            session, name=name, slug=slug, boundary_geojson=boundary_geojson, source=source
        ), True
    existing.name = name
    existing.source = source
    existing.boundary = _boundary_expr(boundary_geojson)
    existing.updated_at = func.now()
    session.flush()
    session.refresh(existing)
    return existing, False


def get(session: Session, area_id: uuid.UUID) -> ServiceArea | None:
    return session.get(ServiceArea, area_id)


def get_by_slug(session: Session, slug: str) -> ServiceArea | None:
    return session.scalars(select(ServiceArea).where(ServiceArea.slug == slug)).one_or_none()


def list_all(session: Session) -> list[ServiceArea]:
    """Deterministic order: name, then slug."""
    return list(session.scalars(select(ServiceArea).order_by(ServiceArea.name, ServiceArea.slug)))
