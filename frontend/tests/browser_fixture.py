"""Isolated browser-QA API. All values/geometries are synthetic test fixtures.

Run from the repository root: backend/.venv/bin/python frontend/tests/browser_fixture.py
Never use this server as an analysis source. No database, files or external network is used.
"""

import json
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import h3
from app.scoring.engine import MetricInput, score_area

KEYS = [
    "intersection_density",
    "road_density",
    "avg_node_degree",
    "network_directness",
    "metadata_completeness",
]
WEIGHTS = dict(zip(KEYS, [0.25, 0.25, 0.2, 0.15, 0.15], strict=True))
NAMES = ["Foster City", "Mountain View", "San Jose"]
VALUES = [
    [0.7, 0.6, 0.7, 0.8, 0.55],
    [0.85, 0.8, 0.7, 0.9, 0.8],
    [0.6, 0.7, 0.65, 0.6, None],
]
CENTERS = [(37.56, -122.27), (37.39, -122.08), (37.33, -121.89)]
IDS = [f"00000000-0000-4000-8000-{i + 1:012}" for i in range(3)]
RUN = {
    "id": "10000000-0000-4000-8000-000000000001",
    "status": "succeeded",
    "pipeline_version": "test-fixture",
    "started_at": "2026-10-30T16:00:00Z",
    "completed_at": "2026-10-30T16:01:00Z",
}
MODEL = {
    "id": "20000000-0000-4000-8000-000000000001",
    "name": "Browser QA fixture",
    "version": "test-only",
    "weights": WEIGHTS,
    "is_default": True,
    "normalization_version": "test-only",
}
SOURCE = {
    "source": "SYNTHETIC BROWSER TEST FIXTURE",
    "note": "Not real analysis. Do not use these values or geometries for decisions.",
}


def scored(i, weights=WEIGHTS):
    result = score_area(
        {
            key: MetricInput(value, 0.85, value)
            for key, value in zip(KEYS, VALUES[i], strict=True)
        },
        weights,
    )
    components = [
        {
            **asdict(c),
            "contribution": c.contribution
            if c.normalized_value is not None and result.score is not None
            else None,
            "display_name": c.metric.replace("_", " ").title(),
        }
        for c in result.components
    ]
    return {
        "service_area_id": IDS[i],
        "name": NAMES[i],
        "slug": NAMES[i].lower().replace(" ", "-"),
        "score": result.score,
        "confidence": result.confidence,
        "rank": None,
        "components": components,
        "strengths": [],
        "risks": [],
        "warnings": ["synthetic_browser_test_fixture", *result.warnings],
        "peer_outliers": [],
        "run": {**RUN, "id": f"10000000-0000-4000-8000-{i + 1:012}"},
    }


def ranked(ids, weights=WEIGHTS):
    areas = [scored(IDS.index(id), weights) for id in ids]
    scores = sorted(
        {round(a["score"], 6) for a in areas if a["score"] is not None}, reverse=True
    )
    for a in areas:
        a["rank"] = (
            scores.index(round(a["score"], 6)) + 1 if a["score"] is not None else None
        )
    return areas


def geometry(i):
    lat, lon = CENTERS[i]
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [lon - 0.025, lat - 0.025],
                    [lon + 0.025, lat - 0.025],
                    [lon + 0.025, lat + 0.025],
                    [lon - 0.025, lat + 0.025],
                    [lon - 0.025, lat - 0.025],
                ]
            ]
        ],
    }


def get_payload(path, query):
    if path == "/health":
        return {"status": "test-fixture"}
    if path.endswith("/scoring-models"):
        return {"items": [MODEL]}
    if path == "/api/v1/service-areas":
        return {
            "items": [
                {
                    "id": a["service_area_id"],
                    "name": a["name"],
                    "slug": a["slug"],
                    "source": "synthetic-browser-test-fixture",
                    "score": a["score"],
                    "confidence": a["confidence"],
                    "rank": a["rank"],
                    "analysis_run_id": a["run"]["id"],
                    "last_run_at": RUN["completed_at"],
                }
                for a in ranked(IDS)
            ],
            "total": 3,
            "limit": 200,
            "offset": 0,
        }
    parts = path.strip("/").split("/")
    i = IDS.index(parts[3])
    suffix = parts[4] if len(parts) > 4 else "detail"
    area = ranked(IDS)[i]
    if suffix == "detail":
        lat, lon = CENTERS[i]
        return {
            "id": IDS[i],
            "name": NAMES[i],
            "source": "synthetic-browser-test-fixture",
            "boundary": geometry(i),
            "bbox": [lon - 0.025, lat - 0.025, lon + 0.025, lat + 0.025],
        }
    if suffix == "summary":
        return {
            **area,
            "id": IDS[i],
            "scoring_model": MODEL,
            "ranked_areas": 3,
            "finding_counts": {"critical": 0, "warning": 1, "info": 0},
        }
    simulation = {
        "id": f"30000000-0000-4000-8000-{i + 1:012}",
        "analysis_run_id": area["run"]["id"],
        "seed": 42 + i,
        "generator_version": "browser-fixture",
        "parameters": {"routes": 500, "source": "synthetic-browser-fixture"},
        "simulated_start_at": RUN["started_at"],
        "created_at": RUN["completed_at"],
        "synthetic": True,
    }
    if suffix == "simulations":
        return {
            "items": [simulation],
            "total": 1,
            "limit": 200,
            "offset": 0,
            "synthetic": True,
        }
    if suffix == "operations":
        return {
            "service_area_id": IDS[i],
            "simulation": simulation,
            "synthetic": True,
            "route_count": 500,
            "completion_rate": 0.92,
            "intervention_rate": 0.16,
            "mean_trip_duration_minutes": 24.5,
            "issue_count": 15,
            "open_issues": 3,
            "resolved_issues": 12,
            "mean_resolution_hours": 8.5,
            "issues_by_severity": {"info": 7, "warning": 5, "critical": 3},
            "days": [
                {
                    "date": "2026-10-30",
                    "routes": 500,
                    "completed": 460,
                    "interventions": 80,
                    "completion_rate": 0.92,
                    "mean_duration_minutes": 24.5,
                }
            ],
        }
    if suffix == "metrics":
        return {
            "service_area_id": IDS[i],
            "run": area["run"],
            "analyzed_at": RUN["completed_at"],
            "source": SOURCE,
            "metrics": [
                {
                    "key": key,
                    "display_name": key.replace("_", " ").title(),
                    "description": "Synthetic browser test metric; not real analysis",
                    "unit": "test units",
                    "higher_is_better": True,
                    "normalization_method": "minmax_fixed",
                    "ref_min": 0,
                    "ref_max": 1,
                    "version": "test-only",
                    "raw_value": value,
                    "normalized_value": value,
                    "confidence": 0.85 if value is not None else None,
                }
                for key, value in zip(KEYS, VALUES[i], strict=True)
            ],
        }
    if suffix == "quality":
        return {
            "service_area_id": IDS[i],
            "run": area["run"],
            "analyzed_at": RUN["completed_at"],
            "source": SOURCE,
            "finding_counts": {"critical": 0, "warning": 1, "info": 0},
            "findings": [
                {
                    "rule_key": "DQ-002",
                    "severity": "warning",
                    "message": "Synthetic test warning: review metadata completeness.",
                    "affected_fraction": 0.3,
                }
            ],
            "completeness": {
                "cells_count": 100,
                "low_confidence_cells": 12,
                "low_confidence_share": 0.12,
                "low_confidence_threshold": 0.5,
                "metrics": [
                    {"metric": key, "null_cells": index * 2, "null_share": index * 0.02}
                    for index, key in enumerate(KEYS)
                ],
            },
        }
    if suffix == "cells":
        metric = query.get("metric", ["overall_score"])[0]
        bbox = [float(x) for x in query["bbox"][0].split(",")]
        features = []
        for j, cell in enumerate(sorted(h3.geo_to_cells(geometry(i), 9))):
            lat, lon = h3.cell_to_latlng(cell)
            if not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
                continue
            val = None if j % 17 == 0 else (j % 10) / 10
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]
                        ],
                    },
                    "properties": {
                        "h3_index": cell,
                        "raw_value": val if metric != "overall_score" else None,
                        "normalized_value": val if metric != "overall_score" else None,
                        "score": val * 100
                        if metric == "overall_score" and val is not None
                        else None,
                        "confidence": 0.3 if j % 7 == 0 else 0.9,
                        "overlap_ratio": 1,
                    },
                }
            )
        return {
            "type": "FeatureCollection",
            "features": features[:2000],
            "metric": metric,
            "analysis_run_id": RUN["id"],
            "limit": 2000,
            "truncated": len(features) > 2000,
        }
    raise ValueError("Unknown test route")


class Handler(BaseHTTPRequestHandler):
    def send(self, status, payload):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        self.send(200, {})

    def do_GET(self):
        try:
            url = urlparse(self.path)
            self.send(200, get_payload(url.path, parse_qs(url.query)))
        except (ValueError, KeyError, IndexError):
            self.send(404, {"error": {"message": "Unknown browser test fixture"}})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            weights = body.get("weights", WEIGHTS)
            result = {
                "scoring_model": {**MODEL, "weights": weights},
                "areas": ranked(body["service_area_ids"], weights),
            }
            if self.path.endswith("preview"):
                result["temporary"] = True
            self.send(200, result)
        except (ValueError, KeyError):
            self.send(422, {"error": {"message": "Invalid browser test request"}})

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print(
        "SYNTHETIC browser fixture API: http://127.0.0.1:8011 — test data only",
        flush=True,
    )
    ThreadingHTTPServer(("127.0.0.1", 8011), Handler).serve_forever()
