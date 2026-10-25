from app.quality.rules import (
    QualityConfig,
    RunQualityInputs,
    evaluate_run_rules,
    peer_outlier_findings,
)
from app.schemas import Severity

CFG = QualityConfig()
REQUIRED = ("m1", "m2")


def inputs(**kw: object) -> RunQualityInputs:
    base: dict[str, object] = {
        "area_metrics": {"m1": 1.0, "m2": 2.0, "metadata_completeness": 0.9},
        "required_metrics": REQUIRED,
        "area_km2": 50.0,
        "node_count": 1000,
        "edge_count": 5000,
    }
    base.update(kw)
    return RunQualityInputs(**base)  # type: ignore[arg-type]


def keys(f: list) -> list[str]:  # type: ignore[type-arg]
    return [x.rule_key for x in f]


def test_clean_run_has_no_findings() -> None:
    assert evaluate_run_rules(inputs(), CFG) == []


def test_dq001_missing_required_metric() -> None:
    f = evaluate_run_rules(
        inputs(area_metrics={"m1": 1.0, "m2": None, "metadata_completeness": 0.9}), CFG
    )
    assert keys(f) == ["DQ-001"]
    assert f[0].severity == Severity.CRITICAL
    assert f[0].affected_fraction == 0.5
    assert f[0].metadata["metrics"] == ["m2"]


def test_dq001_absent_key_counts_and_zero_does_not() -> None:
    f = evaluate_run_rules(inputs(area_metrics={"m1": 0.0, "metadata_completeness": 0.9}), CFG)
    assert keys(f) == ["DQ-001"]
    assert f[0].metadata["metrics"] == ["m2"]


def test_dq002_low_completeness() -> None:
    f = evaluate_run_rules(
        inputs(area_metrics={"m1": 1.0, "m2": 1.0, "metadata_completeness": 0.3}), CFG
    )
    assert keys(f) == ["DQ-002"]
    assert f[0].severity == Severity.WARNING
    assert f[0].affected_fraction == 0.7


def test_dq002_not_triggered_by_none_or_boundary() -> None:
    f = evaluate_run_rules(
        inputs(area_metrics={"m1": 1.0, "m2": 1.0, "metadata_completeness": None}), CFG
    )
    assert "DQ-002" not in keys(f)
    f = evaluate_run_rules(
        inputs(area_metrics={"m1": 1.0, "m2": 1.0, "metadata_completeness": 0.5}), CFG
    )
    assert f == []


def test_dq003_small_area() -> None:
    f = evaluate_run_rules(inputs(area_km2=1.5, edge_count=5000), CFG)
    assert keys(f) == ["DQ-003"]
    assert f[0].severity == Severity.WARNING
    assert evaluate_run_rules(inputs(area_km2=2.0), CFG) == []


def test_dq004_few_nodes() -> None:
    f = evaluate_run_rules(inputs(node_count=99), CFG)
    assert keys(f) == ["DQ-004"]
    assert f[0].severity == Severity.CRITICAL
    assert evaluate_run_rules(inputs(node_count=100), CFG) == []


def test_dq005_too_few_edges() -> None:
    f = evaluate_run_rules(inputs(area_km2=50.0, edge_count=999), CFG)  # needs 1000
    assert keys(f) == ["DQ-005"]
    assert f[0].severity == Severity.CRITICAL
    assert f[0].metadata["expected_min_edges"] == 1000.0
    assert evaluate_run_rules(inputs(area_km2=50.0, edge_count=1000), CFG) == []


def test_config_thresholds_override() -> None:
    cfg = QualityConfig(min_nodes=5000)
    assert keys(evaluate_run_rules(inputs(), cfg)) == ["DQ-004"]


def test_dq006_outlier_flagged() -> None:
    vals = {"a": 10.0, "b": 11.0, "c": 12.0, "d": 100.0}
    f = peer_outlier_findings(vals, "m1")
    assert [x.metadata["area"] for x in f] == ["d"]
    assert f[0].rule_key == "DQ-006"
    assert f[0].severity == Severity.INFO


def test_dq006_needs_three_areas_and_ignores_none() -> None:
    assert peer_outlier_findings({"a": 1.0, "b": 100.0}, "m1") == []
    assert peer_outlier_findings({"a": 1.0, "b": 100.0, "c": None}, "m1") == []


def test_dq006_no_outlier_in_tight_group() -> None:
    assert peer_outlier_findings({"a": 10.0, "b": 11.0, "c": 12.0}, "m1") == []


def test_dq006_zero_mad() -> None:
    f = peer_outlier_findings({"a": 5.0, "b": 5.0, "c": 5.0, "d": 9.0}, "m1")
    assert [x.metadata["area"] for x in f] == ["d"]
    assert peer_outlier_findings({"a": 5.0, "b": 5.0, "c": 5.0}, "m1") == []
