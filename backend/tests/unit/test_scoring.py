import pytest

from app.scoring.engine import (
    InvalidWeightsError,
    MetricInput,
    score_area,
)

W = {"a": 0.5, "b": 0.3, "c": 0.2}


def inp(n: float | None, c: float | None = 1.0, raw: float | None = None) -> MetricInput:
    return MetricInput(normalized_value=n, confidence=c, raw_value=raw)


def test_valid_weights_produce_expected_score() -> None:
    r = score_area({"a": inp(1.0), "b": inp(0.5), "c": inp(0.0)}, W)
    assert r.score == pytest.approx(65.0)  # 100*(0.5+0.15+0)
    assert r.confidence == pytest.approx(1.0)
    assert r.warnings == []


@pytest.mark.parametrize(
    "weights",
    [
        {"a": 0.5, "b": 0.3, "c": 0.3},
        {"a": 0.5, "b": 0.3, "c": 0.1},
        {"a": 1.2, "b": -0.2, "c": 0.0},
        {"a": 0.5, "b": 0.5},
        {"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.1},
    ],
)
def test_invalid_weights_rejected(weights: dict[str, float]) -> None:
    inputs = {k: inp(0.5) for k in weights}
    with pytest.raises(InvalidWeightsError):
        score_area(inputs, weights, required_metrics=set(W))
    assert issubclass(InvalidWeightsError, ValueError)


def test_weights_not_summing_to_one_rejected_without_required() -> None:
    with pytest.raises(InvalidWeightsError, match="sum"):
        score_area({"a": inp(1.0)}, {"a": 0.5, "b": 0.4})


def test_missing_metric_handled_explicitly() -> None:
    r = score_area({"a": inp(1.0), "b": inp(0.0), "c": inp(None, None)}, W)
    # available 0.8: a -> 0.625, b -> 0.375 ; score = 62.5
    assert r.score == pytest.approx(62.5)
    assert "missing_metric:c" in r.warnings
    c = r.components[2]
    assert c.normalized_value is None and c.effective_weight == 0.0
    assert c.contribution == 0.0 and c.weight == 0.2
    assert r.components[0].effective_weight == pytest.approx(0.625)
    # confidence = 0.8 * 1.0
    assert r.confidence == pytest.approx(0.8)


def test_metric_absent_from_inputs_is_missing() -> None:
    r = score_area({"a": inp(1.0), "b": inp(1.0)}, W)
    assert "missing_metric:c" in r.warnings
    assert r.score == pytest.approx(100.0)


def test_zero_is_not_missing() -> None:
    r = score_area({"a": inp(0.0, raw=0.0), "b": inp(0.0), "c": inp(0.0)}, W)
    assert r.score == 0.0
    assert r.warnings == []
    assert r.components[0].raw_value == 0.0


def test_low_confidence_reduces_confidence() -> None:
    hi = score_area({"a": inp(0.5, 1.0), "b": inp(0.5, 1.0), "c": inp(0.5, 1.0)}, W)
    lo = score_area({"a": inp(0.5, 0.2), "b": inp(0.5, 1.0), "c": inp(0.5, 1.0)}, W)
    assert lo.confidence < hi.confidence
    assert lo.confidence == pytest.approx(0.5 * 0.2 + 0.3 + 0.2)
    assert lo.score == hi.score


def test_missing_confidence_treated_as_zero_with_warning() -> None:
    r = score_area({"a": inp(0.5, None), "b": inp(0.5, 1.0), "c": inp(0.5, 1.0)}, W)
    assert "missing_confidence:a" in r.warnings
    assert r.confidence == pytest.approx(0.5)


def test_contributions_sum_to_score() -> None:
    r = score_area({"a": inp(0.37), "b": inp(0.91), "c": inp(None, None)}, W)
    assert r.score is not None
    assert sum(c.contribution for c in r.components) == pytest.approx(r.score)
    assert r.components[0].contribution == pytest.approx(100 * (0.5 / 0.8) * 0.37)


@pytest.mark.parametrize("n", [0.0, 0.25, 1.0])
def test_score_within_range(n: float) -> None:
    r = score_area({"a": inp(n), "b": inp(n), "c": inp(n)}, W)
    assert r.score is not None and 0.0 <= r.score <= 100.0
    assert 0.0 <= r.confidence <= 1.0


def test_insufficient_data_gives_null_score() -> None:
    r = score_area({"a": inp(None, None), "b": inp(0.9), "c": inp(0.9)}, W)  # avail 0.5? no
    assert r.score is not None  # exactly 0.5 is sufficient
    r2 = score_area({"a": inp(None, None), "b": inp(0.9), "c": inp(None, None)}, W)
    assert r2.score is None
    assert "insufficient_data" in r2.warnings
    assert "missing_metric:a" in r2.warnings
    assert r2.confidence == pytest.approx(0.3 * 1.0)
    assert all(c.contribution == 0.0 for c in r2.components)


def test_all_missing() -> None:
    r = score_area({}, W)
    assert r.score is None and r.confidence == 0.0
    assert "insufficient_data" in r.warnings


def test_component_order_follows_weights() -> None:
    r = score_area({"c": inp(0.1), "a": inp(0.2), "b": inp(0.3)}, W)
    assert [c.metric for c in r.components] == ["a", "b", "c"]


def test_required_metrics_exact_match() -> None:
    r = score_area({k: inp(1.0) for k in W}, W, required_metrics=set(W))
    assert r.score == pytest.approx(100.0)
    with pytest.raises(InvalidWeightsError, match=r"missing|unexpected|keys"):
        score_area({"a": inp(1.0)}, {"a": 1.0}, required_metrics=set(W))
