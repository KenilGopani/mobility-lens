import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas import (
    AreaMetricRead,
    AreaScoreRead,
    DataQualityFindingRead,
    MetricDefinitionRead,
    ScoringModelRead,
    Severity,
)

RUN = uuid.uuid4()
NOW = datetime.now(UTC)


def test_metric_fields_nullable_and_zero_preserved() -> None:
    unavailable = AreaMetricRead(analysis_run_id=RUN, metric_key="k")
    assert (unavailable.raw_value, unavailable.normalized_value) == (None, None)
    zero = AreaMetricRead(analysis_run_id=RUN, metric_key="k", raw_value=0, normalized_value=0)
    assert zero.raw_value == 0.0
    assert zero.normalized_value == 0.0


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_normalized_out_of_range_rejected(bad: float) -> None:
    with pytest.raises(ValidationError):
        AreaMetricRead(analysis_run_id=RUN, metric_key="k", normalized_value=bad)


def test_severity_enum() -> None:
    f = DataQualityFindingRead(
        id=uuid.uuid4(), analysis_run_id=RUN, rule_key="DQ-001", severity="critical", message="m"
    )
    assert f.severity is Severity.CRITICAL
    with pytest.raises(ValidationError):
        DataQualityFindingRead(
            id=uuid.uuid4(), analysis_run_id=RUN, rule_key="r", severity="fatal", message="m"
        )
    with pytest.raises(ValidationError):
        DataQualityFindingRead(
            id=uuid.uuid4(),
            analysis_run_id=RUN,
            rule_key="r",
            severity="info",
            message="m",
            affected_fraction=1.5,
        )


def test_score_nullable_and_bounded() -> None:
    kwargs = {
        "analysis_run_id": RUN,
        "scoring_model_id": uuid.uuid4(),
        "confidence": 0.5,
        "component_breakdown": {},
        "calculated_at": NOW,
    }
    assert AreaScoreRead(**kwargs).score is None  # type: ignore[arg-type]
    assert AreaScoreRead(score=0, **kwargs).score == 0.0  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        AreaScoreRead(score=100.5, **kwargs)  # type: ignore[arg-type]


def test_metric_definition_degenerate_range_rejected() -> None:
    base = {
        "key": "k",
        "display_name": "K",
        "description": "d",
        "unit": "u",
        "higher_is_better": True,
        "normalization_method": "minmax_fixed",
        "version": "v1",
    }
    MetricDefinitionRead(ref_min=0, ref_max=1, **base)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        MetricDefinitionRead(ref_min=1, ref_max=1, **base)  # type: ignore[arg-type]


def _model(weights: dict[str, float]) -> ScoringModelRead:
    return ScoringModelRead(
        id=uuid.uuid4(),
        name="n",
        version="v1",
        weights=weights,
        normalization_version="v1",
        is_default=False,
        created_at=NOW,
    )


def test_weights_validation() -> None:
    _model({"a": 0.5, "b": 0.5})
    with pytest.raises(ValidationError):
        _model({"a": 0.5, "b": 0.6})
    with pytest.raises(ValidationError):
        _model({"a": 1.5, "b": -0.5})
