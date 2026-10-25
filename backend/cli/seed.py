"""Idempotent seed data. Pure functions over a Session; the CLI wraps them."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import MetricDefinition
from app.repositories import scoring_models, service_areas

BOUNDARY_DIR = Path(__file__).resolve().parent.parent / "data" / "boundaries"

# slug -> display name. Boundaries are produced in Phase 3 (OSM geocoding); no geometry is
# invented here.
MVP_AREAS: dict[str, str] = {
    "foster-city": "Foster City",
    "san-jose": "San Jose",
    "mountain-view": "Mountain View",
}

METRIC_VERSION = "v1"

# Provisional reference ranges (docs/scoring-model.md); frozen as v1 after Phase 4 calibration.
METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "intersection_density",
        "display_name": "Intersection density",
        "description": "Nodes with street_count >= 3 per km2 of land area.",
        "unit": "per km2",
        "ref_min": 0.0,
        "ref_max": 150.0,
    },
    {
        "key": "road_density",
        "display_name": "Road density",
        "description": "Drivable edge length (each physical street once) per km2.",
        "unit": "km/km2",
        "ref_min": 0.0,
        "ref_max": 25.0,
    },
    {
        "key": "avg_node_degree",
        "display_name": "Average node degree",
        "description": "Mean street_count over nodes inside the region.",
        "unit": "streets/node",
        "ref_min": 2.0,
        "ref_max": 3.5,
    },
    {
        "key": "network_directness",
        "display_name": "Network directness",
        "description": "1 / circuity_avg, length-weighted.",
        "unit": "ratio",
        "ref_min": 0.7,
        "ref_max": 1.0,
    },
    {
        "key": "metadata_completeness",
        "display_name": "Metadata completeness",
        "description": "Mean fraction of drivable edges tagged maxspeed, lanes and name.",
        "unit": "fraction",
        "ref_min": 0.0,
        "ref_max": 1.0,
    },
]

BASELINE_WEIGHTS: dict[str, float] = {
    "intersection_density": 0.25,
    "road_density": 0.25,
    "avg_node_degree": 0.20,
    "network_directness": 0.15,
    "metadata_completeness": 0.15,
}


@dataclass
class SeedReport:
    created: list[str]
    updated: list[str]
    missing: list[str]


def seed_service_areas(session: Session, boundary_dir: Path = BOUNDARY_DIR) -> SeedReport:
    """Upsert areas whose `<slug>.geojson` exists; report (never fabricate) the rest."""
    report = SeedReport([], [], [])
    for slug, name in MVP_AREAS.items():
        path = boundary_dir / f"{slug}.geojson"
        if not path.is_file():
            report.missing.append(slug)
            continue
        geojson = _read_geometry(path)
        _, created = service_areas.upsert_by_slug(
            session,
            name=name,
            slug=slug,
            boundary_geojson=geojson,
            source=f"file:data/boundaries/{path.name}",
        )
        (report.created if created else report.updated).append(slug)
    return report


def _read_geometry(path: Path) -> dict[str, Any]:
    """Accept a bare geometry, a Feature, or a single-feature FeatureCollection."""
    doc = json.loads(path.read_text())
    if doc.get("type") == "FeatureCollection":
        features = doc.get("features", [])
        if len(features) != 1:
            raise ValueError(f"{path.name}: expected exactly one feature, got {len(features)}")
        doc = features[0]
    if doc.get("type") == "Feature":
        doc = doc["geometry"]
    if doc.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"{path.name}: boundary must be a Polygon or MultiPolygon")
    geometry: dict[str, Any] = doc
    return geometry


def seed_metric_definitions(session: Session) -> SeedReport:
    report = SeedReport([], [], [])
    for spec in METRIC_DEFINITIONS:
        row = session.get(MetricDefinition, spec["key"])
        values = {
            **spec,
            "higher_is_better": True,
            "normalization_method": "minmax_fixed",
            "version": METRIC_VERSION,
        }
        if row is None:
            session.add(MetricDefinition(**values))
            report.created.append(spec["key"])
        else:
            for k, v in values.items():
                setattr(row, k, v)
            report.updated.append(spec["key"])
    session.flush()
    return report


def seed_scoring_model(session: Session) -> SeedReport:
    existing = scoring_models.get_by_name_version(session, "baseline", "v1")
    if existing is None:
        scoring_models.create(
            session,
            name="baseline",
            version="v1",
            weights=dict(BASELINE_WEIGHTS),
            normalization_version=METRIC_VERSION,
            is_default=True,
        )
        return SeedReport(["baseline:v1"], [], [])
    existing.weights = dict(BASELINE_WEIGHTS)
    existing.normalization_version = METRIC_VERSION
    if not existing.is_default:
        scoring_models.set_default(session, existing)
    session.flush()
    return SeedReport([], ["baseline:v1"], [])
