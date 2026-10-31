"""Opt-in local HTTP measurements and a parameterized PostGIS viewport query plan."""

import json
import math
import statistics
import time
from datetime import UTC, datetime
from typing import Any
from urllib.request import Request, urlopen

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine


def _request(base: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    req = Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read())  # type: ignore[no-any-return]


def benchmark(base: str, samples: int = 10) -> dict[str, Any]:
    if not 1 <= samples <= 100:
        raise ValueError("samples must be between 1 and 100")
    areas = _request(base, "/api/v1/service-areas?limit=200")["items"]
    if len(areas) < 2:
        raise ValueError("At least two analyzed service areas are required")
    largest = next((a for a in areas if a["slug"] == "san-jose"), areas[0])
    detail = _request(base, f"/api/v1/service-areas/{largest['id']}")
    west, south, east, north = detail["bbox"]
    cx, cy = (west + east) / 2, (south + north) / 2
    bbox = [
        cx - (east - west) * 0.1,
        cy - (north - south) * 0.1,
        cx + (east - west) * 0.1,
        cy + (north - south) * 0.1,
    ]
    root = f"/api/v1/service-areas/{largest['id']}"
    ids = [a["id"] for a in areas[:3]]
    cases = [
        ("summary", root + "/summary", None, 300),
        ("comparison", "/api/v1/comparisons", {"service_area_ids": ids}, 500),
        (
            "viewport",
            root + "/cells?metric=overall_score&limit=2000&bbox=" + ",".join(map(str, bbox)),
            None,
            500,
        ),
        ("full_area_cells", root + "/cells?metric=overall_score&limit=2000", None, None),
        ("synthetic_operations", root + "/operations", None, None),
    ]
    measurements = []
    for name, path, body, target in cases:
        _request(base, path, body)  # warm connections and caches; measured separately below
        elapsed = []
        for _ in range(samples):
            started = time.perf_counter()
            _request(base, path, body)
            elapsed.append((time.perf_counter() - started) * 1000)
        p95 = sorted(elapsed)[math.ceil(0.95 * len(elapsed)) - 1]
        measurements.append(
            {
                "name": name,
                "samples": samples,
                "median_ms": round(statistics.median(elapsed), 2),
                "p95_ms": round(p95, 2),
                "target_ms": target,
                "meets_target_p95": p95 < target if target else None,
            }
        )
    engine = make_engine(get_settings().database_url)
    with engine.connect() as conn:
        plan = conn.execute(
            text("""EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT c.h3_index FROM analysis_run_cells c
            JOIN h3_cells h ON h.h3_index=c.h3_index
            WHERE c.analysis_run_id=:run_id
            AND ST_Intersects(h.boundary, ST_MakeEnvelope(:w,:s,:e,:n,4326))
            ORDER BY c.h3_index LIMIT 2001"""),
            {
                "run_id": largest["analysis_run_id"],
                "w": bbox[0],
                "s": bbox[1],
                "e": bbox[2],
                "n": bbox[3],
            },
        ).scalar_one()
    engine.dispose()
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "transport": "local HTTP + real PostGIS; warm runs, no external OSM calls",
        "area": largest["slug"],
        "viewport": bbox,
        "measurements": measurements,
        "viewport_query_plan": plan,
    }
