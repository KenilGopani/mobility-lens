"""Pydantic read models. Metric values are nullable: None means unavailable, 0 is a real value."""

import math
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)


class ServiceAreaRead(_Read):
    id: uuid.UUID
    name: str
    slug: str
    source: str
    created_at: datetime
    updated_at: datetime


class AnalysisRunRead(_Read):
    id: uuid.UUID
    service_area_id: uuid.UUID
    pipeline_version: str
    parameters: dict[str, Any]
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    source_metadata: dict[str, Any]


class MetricDefinitionRead(_Read):
    key: str
    display_name: str
    description: str
    unit: str
    higher_is_better: bool
    normalization_method: str
    ref_min: float | None = None
    ref_max: float | None = None
    version: str

    @model_validator(mode="after")
    def _range_not_degenerate(self) -> Self:
        if self.ref_min is not None and self.ref_max is not None and self.ref_min == self.ref_max:
            raise ValueError("ref_min and ref_max must differ")
        return self


class CellMetricRead(_Read):
    analysis_run_id: uuid.UUID
    h3_index: str
    metric_key: str
    raw_value: float | None = None
    normalized_value: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AreaMetricRead(_Read):
    analysis_run_id: uuid.UUID
    metric_key: str
    raw_value: float | None = None
    normalized_value: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ScoringModelRead(_Read):
    id: uuid.UUID
    name: str
    version: str
    weights: dict[str, float]
    normalization_version: str
    is_default: bool
    created_at: datetime

    @model_validator(mode="after")
    def _weights_valid(self) -> Self:
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("weights must be >= 0")
        if not math.isclose(sum(self.weights.values()), 1.0, abs_tol=1e-6):
            raise ValueError("weights must sum to 1.0")
        return self


class AreaScoreRead(_Read):
    analysis_run_id: uuid.UUID
    scoring_model_id: uuid.UUID
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    component_breakdown: dict[str, Any]
    calculated_at: datetime


class DataQualityFindingRead(_Read):
    id: uuid.UUID
    analysis_run_id: uuid.UUID
    rule_key: str
    severity: Severity
    message: str
    affected_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
