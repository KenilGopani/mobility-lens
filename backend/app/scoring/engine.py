"""Pure weighted scoring with explicit missing-data handling. See docs/scoring-model.md."""

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

WEIGHT_TOLERANCE = 1e-6
_EPS = 1e-9


class InvalidWeightsError(ValueError):
    """Scoring weights violate the model's invariants."""


@dataclass(frozen=True)
class MetricInput:
    normalized_value: float | None
    confidence: float | None = None
    raw_value: float | None = None


@dataclass(frozen=True)
class ComponentResult:
    metric: str
    raw_value: float | None
    normalized_value: float | None
    weight: float
    effective_weight: float
    contribution: float
    confidence: float | None


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    confidence: float
    components: list[ComponentResult]
    warnings: list[str] = field(default_factory=list)


def validate_weights(
    weights: Mapping[str, float], required_metrics: Collection[str] | None
) -> None:
    if required_metrics is not None:
        required = set(required_metrics)
        missing = sorted(required - weights.keys())
        unexpected = sorted(weights.keys() - required)
        if missing or unexpected:
            raise InvalidWeightsError(
                f"weight keys must match required metrics exactly "
                f"(missing: {missing}, unexpected: {unexpected})"
            )
    for key, w in weights.items():
        if math.isnan(w) or w < 0:
            raise InvalidWeightsError(f"weight for {key!r} must be >= 0, got {w}")
    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise InvalidWeightsError(f"weights must sum to 1.0 (got {total})")


def score_area(
    components_input: Mapping[str, MetricInput],
    weights: Mapping[str, float],
    *,
    required_metrics: Collection[str] | None = None,
    min_available_weight: float = 0.5,
) -> ScoreResult:
    """Compute score (0-100 or None) and confidence. Metrics absent from input count as missing."""
    validate_weights(weights, required_metrics)

    warnings: list[str] = []
    available: list[str] = []
    for key in weights:
        m = components_input.get(key)
        n = None if m is None else m.normalized_value
        if n is None or math.isnan(n):
            warnings.append(f"missing_metric:{key}")
        else:
            available.append(key)

    available_weight = sum(weights[k] for k in available)
    sufficient = available_weight > 0 and available_weight >= min_available_weight - _EPS
    if not sufficient:
        warnings.append("insufficient_data")

    components: list[ComponentResult] = []
    score = 0.0
    conf_sum = 0.0
    for key, w in weights.items():
        m = components_input.get(key)
        raw = None if m is None else m.raw_value
        conf = None if m is None else m.confidence
        if key not in available or available_weight <= 0:
            components.append(ComponentResult(key, raw, None, w, 0.0, 0.0, conf))
            continue
        assert m is not None and m.normalized_value is not None
        eff = w / available_weight
        if conf is None:
            warnings.append(f"missing_confidence:{key}")
        conf_sum += eff * (conf if conf is not None else 0.0)
        contribution = 100.0 * eff * m.normalized_value if sufficient else 0.0
        score += contribution
        components.append(ComponentResult(key, raw, m.normalized_value, w, eff, contribution, conf))

    confidence = min(1.0, max(0.0, available_weight * conf_sum))
    final = min(100.0, max(0.0, score)) if sufficient else None
    return ScoreResult(final, confidence, components, warnings)
