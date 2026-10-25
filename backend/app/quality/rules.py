"""Pure data-quality rules DQ-001..DQ-006. See docs/scoring-model.md."""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.schemas import Severity

COMPLETENESS_KEY = "metadata_completeness"


@dataclass(frozen=True)
class Finding:
    rule_key: str
    severity: Severity
    message: str
    affected_fraction: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityConfig:
    min_completeness: float = 0.5  # DQ-002
    min_area_km2: float = 2.0  # DQ-003
    min_nodes: int = 100  # DQ-004
    # DQ-005: PROVISIONAL default; calibrate against real Bay Area output (Phase 4).
    min_edges_per_km2: float = 20.0
    outlier_mad_threshold: float = 2.0  # DQ-006
    outlier_min_areas: int = 3  # DQ-006


@dataclass(frozen=True)
class RunQualityInputs:
    area_metrics: Mapping[str, float | None]
    required_metrics: Sequence[str]
    area_km2: float
    node_count: int
    edge_count: int


def dq001_missing_required(inputs: RunQualityInputs) -> list[Finding]:
    missing = [k for k in inputs.required_metrics if inputs.area_metrics.get(k) is None]
    if not missing:
        return []
    return [
        Finding(
            "DQ-001",
            Severity.CRITICAL,
            f"Required metric(s) unavailable: {', '.join(missing)}",
            len(missing) / len(inputs.required_metrics),
            {"metrics": missing},
        )
    ]


def dq002_low_completeness(inputs: RunQualityInputs, config: QualityConfig) -> list[Finding]:
    value = inputs.area_metrics.get(COMPLETENESS_KEY)
    if value is None or value >= config.min_completeness:
        return []
    return [
        Finding(
            "DQ-002",
            Severity.WARNING,
            f"Metadata completeness {value:.2f} is below {config.min_completeness:.2f}",
            min(1.0, max(0.0, 1.0 - value)),
            {"value": value, "threshold": config.min_completeness},
        )
    ]


def dq003_small_area(inputs: RunQualityInputs, config: QualityConfig) -> list[Finding]:
    if inputs.area_km2 >= config.min_area_km2:
        return []
    return [
        Finding(
            "DQ-003",
            Severity.WARNING,
            f"Analysis area {inputs.area_km2:.2f} km2 is below {config.min_area_km2:.2f} km2",
            None,
            {"area_km2": inputs.area_km2, "threshold": config.min_area_km2},
        )
    ]


def dq004_few_nodes(inputs: RunQualityInputs, config: QualityConfig) -> list[Finding]:
    if inputs.node_count >= config.min_nodes:
        return []
    return [
        Finding(
            "DQ-004",
            Severity.CRITICAL,
            f"Only {inputs.node_count} network nodes (minimum {config.min_nodes})",
            None,
            {"node_count": inputs.node_count, "threshold": config.min_nodes},
        )
    ]


def dq005_few_edges(inputs: RunQualityInputs, config: QualityConfig) -> list[Finding]:
    expected = config.min_edges_per_km2 * inputs.area_km2
    if inputs.edge_count >= expected:
        return []
    return [
        Finding(
            "DQ-005",
            Severity.CRITICAL,
            f"OSM fetch returned {inputs.edge_count} edges, expected at least {expected:.0f} "
            f"for {inputs.area_km2:.2f} km2",
            None,
            {"edge_count": inputs.edge_count, "expected_min_edges": expected},
        )
    ]


def evaluate_run_rules(inputs: RunQualityInputs, config: QualityConfig) -> list[Finding]:
    """Evaluate persisted rules DQ-001..DQ-005 in code order."""
    return [
        *dq001_missing_required(inputs),
        *dq002_low_completeness(inputs, config),
        *dq003_small_area(inputs, config),
        *dq004_few_nodes(inputs, config),
        *dq005_few_edges(inputs, config),
    ]


def peer_outlier_findings(
    values_by_area: Mapping[str, float | None],
    metric: str,
    config: QualityConfig | None = None,
) -> list[Finding]:
    """DQ-006 (read-time, not persisted): areas deviating > threshold MAD from the peer median."""
    cfg = config or QualityConfig()
    present = {k: v for k, v in values_by_area.items() if v is not None}
    if len(present) < cfg.outlier_min_areas:
        return []
    median = statistics.median(present.values())
    mad = statistics.median(abs(v - median) for v in present.values())
    findings: list[Finding] = []
    for area, v in present.items():
        dev = abs(v - median)
        if dev > cfg.outlier_mad_threshold * mad:
            findings.append(
                Finding(
                    "DQ-006",
                    Severity.INFO,
                    f"{metric} for {area} ({v:g}) deviates from peer median {median:g}",
                    None,
                    {"area": area, "metric": metric, "value": v, "median": median, "mad": mad},
                )
            )
    return findings
