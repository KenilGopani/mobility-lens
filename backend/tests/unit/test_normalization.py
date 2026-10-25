import math

import pytest

from app.scoring.normalization import normalize


def test_known_minimum() -> None:
    r = normalize(0.0, 0.0, 150.0, True)
    assert r.normalized_value == 0.0
    assert not r.clipped


def test_known_maximum() -> None:
    r = normalize(150.0, 0.0, 150.0, True)
    assert r.normalized_value == 1.0
    assert not r.clipped


def test_midpoint() -> None:
    assert normalize(75.0, 0.0, 150.0, True).normalized_value == pytest.approx(0.5)


def test_inverted_lower_is_better() -> None:
    assert normalize(30.0, 0.0, 100.0, False).normalized_value == pytest.approx(0.7)
    assert normalize(0.0, 0.0, 100.0, False).normalized_value == 1.0


def test_constant_reference_range_rejected() -> None:
    with pytest.raises(ValueError):
        normalize(1.0, 2.0, 2.0, True)


def test_null_input_gives_null() -> None:
    r = normalize(None, 0.0, 1.0, True)
    assert r.normalized_value is None
    assert not r.clipped


def test_nan_treated_as_null() -> None:
    assert normalize(math.nan, 0.0, 1.0, True).normalized_value is None


def test_clipping_flagged() -> None:
    hi = normalize(200.0, 0.0, 150.0, True)
    lo = normalize(-5.0, 0.0, 150.0, True)
    assert (hi.normalized_value, hi.clipped) == (1.0, True)
    assert (lo.normalized_value, lo.clipped) == (0.0, True)
    inv = normalize(200.0, 0.0, 150.0, False)
    assert (inv.normalized_value, inv.clipped) == (0.0, True)


def test_zero_is_a_real_value() -> None:
    r = normalize(0.0, 0.0, 10.0, True)
    assert r.normalized_value == 0.0
    assert r.normalized_value is not None
    assert normalize(0.0, 0.0, 10.0, False).normalized_value == 1.0
