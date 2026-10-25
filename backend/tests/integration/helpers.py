"""Shared builders for integration tests."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import MetricDefinition, ServiceArea
from app.repositories import analysis_runs, service_areas
from app.repositories.inputs import H3CellInput, RunCellInput


def square_geojson(x: float, y: float, size: float = 0.1) -> dict[str, Any]:
    ring = [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]
    return {"type": "Polygon", "coordinates": [ring]}


def make_area(session: Session, slug: str = "test-area", x: float = -122.3) -> ServiceArea:
    return service_areas.create(
        session,
        name=slug.replace("-", " ").title(),
        slug=slug,
        boundary_geojson=square_geojson(x, 37.5),
        source="test",
    )


def make_cell(index: str, x: float, y: float, size: float = 0.01) -> H3CellInput:
    x2, y2 = x + size, y + size
    poly = f"POLYGON(({x} {y}, {x2} {y}, {x2} {y2}, {x} {y2}, {x} {y}))"
    return H3CellInput(index, 9, poly, f"POINT({x + size / 2} {y + size / 2})")


def make_run_with_cells(session: Session, area: ServiceArea, cells: list[H3CellInput]) -> Any:
    run = analysis_runs.create_run(
        session, service_area_id=area.id, pipeline_version="t", parameters={"h3_resolution": 9}
    )
    return run, [RunCellInput(c, 1.0) for c in cells]


def make_metric(session: Session, key: str = "road_density") -> MetricDefinition:
    m = MetricDefinition(
        key=key,
        display_name=key,
        description="d",
        unit="u",
        higher_is_better=True,
        normalization_method="minmax_fixed",
        ref_min=0.0,
        ref_max=1.0,
        version="v1",
    )
    session.add(m)
    session.flush()
    return m
