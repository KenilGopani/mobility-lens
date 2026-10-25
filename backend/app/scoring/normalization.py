"""Fixed-range min-max normalization (``minmax_fixed``). Pure; see docs/scoring-model.md."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizationResult:
    normalized_value: float | None
    clipped: bool


def normalize(
    raw: float | None, ref_min: float, ref_max: float, higher_is_better: bool
) -> NormalizationResult:
    """Normalize ``raw`` to [0, 1] using a fixed reference range.

    ``None`` and NaN map to ``None`` (never 0). Out-of-range values are clipped and flagged.
    """
    if ref_min == ref_max:
        raise ValueError("ref_min and ref_max must differ")
    if raw is None or math.isnan(raw):
        return NormalizationResult(None, False)
    scaled = (raw - ref_min) / (ref_max - ref_min)
    clipped = scaled < 0.0 or scaled > 1.0
    value = min(1.0, max(0.0, scaled))
    if not higher_is_better:
        value = 1.0 - value
    return NormalizationResult(value, clipped)
