"""Real normalization, data-quality and scoring stages wired into the pipeline.

The pipeline (analyze.py) only knows the hook signatures; this module supplies the production
implementations built on app.scoring and app.quality.
"""

import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.models import ScoringModel
from app.quality.rules import Finding, QualityConfig, RunQualityInputs, evaluate_run_rules
from app.repositories import area_scores, metric_definitions, scoring_models
from app.repositories.inputs import AreaMetricInput, CellMetricInput
from app.scoring.engine import MetricInput, ScoreResult, score_area
from app.scoring.normalization import normalize
from pipelines.metrics import METRIC_KEYS

if TYPE_CHECKING:
    from pipelines.analyze import Normalizer, QualityEvaluator


class MissingMetricDefinitionError(LookupError):
    """A computed metric has no row in metric_definitions (run seed-metric-definitions)."""


class MissingScoringModelError(LookupError):
    """No default scoring model exists (run seed-scoring-model)."""


def make_db_normalizer(session: Session) -> "Normalizer":
    """Normalizer using fixed reference ranges from metric_definitions."""

    def normalizer(
        cell_metrics: list[CellMetricInput], area_metrics: list[AreaMetricInput]
    ) -> tuple[list[CellMetricInput], list[AreaMetricInput]]:
        defs = metric_definitions.get_all(session)

        def apply(key: str, raw: float | None) -> tuple[float | None, bool]:
            d = defs.get(key)
            if d is None:
                raise MissingMetricDefinitionError(
                    f"no metric definition for {key!r} (run seed-metric-definitions)"
                )
            if d.ref_min is None or d.ref_max is None:
                raise MissingMetricDefinitionError(f"metric {key!r} has no reference range")
            r = normalize(raw, d.ref_min, d.ref_max, d.higher_is_better)
            return r.normalized_value, r.clipped

        cells_out: list[CellMetricInput] = []
        for c in cell_metrics:
            value, clipped = apply(c.metric_key, c.raw_value)
            cells_out.append(
                CellMetricInput(
                    c.h3_index,
                    c.metric_key,
                    c.raw_value,
                    value,
                    c.confidence,
                    {**(c.metadata or {}), "clipped": clipped},
                )
            )
        areas_out = [
            AreaMetricInput(
                a.metric_key, a.raw_value, apply(a.metric_key, a.raw_value)[0], a.confidence
            )
            for a in area_metrics
        ]
        return cells_out, areas_out

    return normalizer


def make_quality_evaluator(config: QualityConfig) -> "QualityEvaluator":
    from pipelines.analyze import AnalysisContext, FindingInput

    def evaluator(context: AnalysisContext) -> list[FindingInput]:
        inputs = RunQualityInputs(
            area_metrics={m.metric_key: m.raw_value for m in context.area_metrics},
            required_metrics=METRIC_KEYS,
            area_km2=context.area_km2,
            node_count=context.node_count,
            edge_count=context.edge_count,
        )
        findings: list[Finding] = evaluate_run_rules(inputs, config)
        return [
            FindingInput(
                f.rule_key, f.severity.value, f.message, f.affected_fraction, dict(f.metadata)
            )
            for f in findings
        ]

    return evaluator


def quality_config_parameters(config: QualityConfig) -> dict[str, Any]:
    return asdict(config)


def score_and_store(
    session: Session, run_id: uuid.UUID, area_metrics: list[AreaMetricInput]
) -> tuple[ScoringModel, ScoreResult]:
    """Score the run's AREA metrics with the default model and persist an area_scores row."""
    model = scoring_models.get_default(session)
    if model is None:
        raise MissingScoringModelError("no default scoring model (run seed-scoring-model)")
    result = score_area(
        {
            m.metric_key: MetricInput(m.normalized_value, m.confidence, m.raw_value)
            for m in area_metrics
        },
        {k: float(v) for k, v in model.weights.items()},
        required_metrics=METRIC_KEYS,
    )
    area_scores.add(
        session,
        analysis_run_id=run_id,
        scoring_model_id=model.id,
        score=result.score,
        confidence=result.confidence,
        component_breakdown={
            "model": {"name": model.name, "version": model.version},
            "components": [asdict(c) for c in result.components],
            "warnings": list(result.warnings),
        },
    )
    return model, result
