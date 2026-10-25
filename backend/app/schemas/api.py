"""HTTP request/response models for /api/v1. docs/openapi.json is generated from these.

Conventions: every metric-derived number is nullable; ``null`` means unavailable, never 0.
"""

import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.domain import RunStatus, Severity

# ---------------------------------------------------------------- errors


class ErrorBody(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------- shared


class RunRef(BaseModel):
    """Compact analysis-run reference embedded in other responses."""

    id: uuid.UUID
    status: RunStatus
    pipeline_version: str
    started_at: datetime
    completed_at: datetime | None = None


class ScoringModelRef(BaseModel):
    """Weights used for a score. ``id``/``version`` are null for preview weights."""

    id: uuid.UUID | None = None
    name: str
    version: str | None = None
    weights: dict[str, float]


class ScoreComponent(BaseModel):
    metric: str
    display_name: str | None = None
    raw_value: float | None = None
    normalized_value: float | None = None
    weight: float
    effective_weight: float = Field(description="Weight after renormalizing over available metrics")
    contribution: float | None = Field(
        default=None, description="Points added to the score; null when the metric is missing"
    )
    confidence: float | None = None


class MetricHighlight(BaseModel):
    """A strength or risk, derived from the component's normalized value."""

    metric: str
    display_name: str | None = None
    raw_value: float | None = None
    normalized_value: float
    unit: str | None = None


class SeverityCounts(BaseModel):
    info: int = 0
    warning: int = 0
    critical: int = 0


class Finding(BaseModel):
    rule_key: str
    severity: Severity
    message: str
    affected_fraction: float | None = None
    metadata: dict[str, Any] | None = None


class PeerOutlier(BaseModel):
    """DQ-006, computed at read time over the compared set (never persisted)."""

    rule_key: Literal["DQ-006"] = "DQ-006"
    severity: Severity
    metric: str
    message: str
    value: float
    median: float
    mad: float


# ---------------------------------------------------------------- service areas


class ServiceAreaListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    source: str
    score: float | None = None
    confidence: float | None = None
    rank: int | None = Field(default=None, description="Dense rank among all areas; null=unscored")
    analysis_run_id: uuid.UUID | None = None
    last_run_at: datetime | None = Field(
        default=None, description="Completion time of the latest succeeded run"
    )


class ServiceAreaPage(BaseModel):
    items: list[ServiceAreaListItem]
    total: int
    limit: int
    offset: int


class ServiceAreaDetail(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    source: str
    created_at: datetime
    updated_at: datetime
    bbox: list[float] = Field(description="[minLon, minLat, maxLon, maxLat]")
    boundary: dict[str, Any] = Field(description="GeoJSON MultiPolygon geometry, EPSG:4326")


class ServiceAreaSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    scoring_model: ScoringModelRef | None = None
    score: float | None = None
    confidence: float | None = None
    rank: int | None = None
    ranked_areas: int = Field(description="Number of areas with a score")
    components: list[ScoreComponent] = []
    strengths: list[MetricHighlight] = []
    risks: list[MetricHighlight] = []
    warnings: list[str] = []
    finding_counts: SeverityCounts
    run: RunRef | None = None


class MetricValue(BaseModel):
    key: str
    display_name: str
    description: str
    unit: str
    higher_is_better: bool
    normalization_method: str
    ref_min: float | None = None
    ref_max: float | None = None
    version: str
    raw_value: float | None = None
    normalized_value: float | None = None
    confidence: float | None = None


class AreaMetricsResponse(BaseModel):
    service_area_id: uuid.UUID
    run: RunRef
    analyzed_at: datetime | None = Field(
        description="Completion time of the run that produced these metrics"
    )
    source: dict[str, Any] = Field(description="Provenance copied from run.source_metadata")
    metrics: list[MetricValue]


class MetricCompleteness(BaseModel):
    metric: str
    null_cells: int
    null_share: float | None = Field(
        description="Share of run cells with no value; null if 0 cells"
    )


class Completeness(BaseModel):
    cells_count: int
    low_confidence_threshold: float
    low_confidence_cells: int
    low_confidence_share: float | None = None
    metrics: list[MetricCompleteness]


class QualityResponse(BaseModel):
    service_area_id: uuid.UUID
    run: RunRef
    analyzed_at: datetime | None = None
    source: dict[str, Any]
    findings: list[Finding]
    finding_counts: SeverityCounts
    completeness: Completeness


class CellProperties(BaseModel):
    h3_index: str
    raw_value: float | None = None
    normalized_value: float | None = None
    confidence: float | None = None
    overlap_ratio: float
    score: float | None = Field(
        default=None, description="Per-cell weighted score 0-100; only for metric=overall_score"
    )


class CellFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: CellProperties


class CellsResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    metric: str
    analysis_run_id: uuid.UUID
    limit: int
    truncated: bool
    features: list[CellFeature]


# ---------------------------------------------------------------- comparison / preview


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_area_ids: list[uuid.UUID] = Field(min_length=2, max_length=3)
    scoring_model_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _distinct(self) -> Self:
        if len(set(self.service_area_ids)) != len(self.service_area_ids):
            raise ValueError("service_area_ids must be distinct")
        return self


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_area_ids: list[uuid.UUID] = Field(min_length=1, max_length=3)
    weights: dict[str, float] = Field(min_length=1)

    @model_validator(mode="after")
    def _distinct(self) -> Self:
        if len(set(self.service_area_ids)) != len(self.service_area_ids):
            raise ValueError("service_area_ids must be distinct")
        return self


class AreaScoreResult(BaseModel):
    service_area_id: uuid.UUID
    name: str
    slug: str
    score: float | None = None
    confidence: float | None = None
    rank: int | None = None
    components: list[ScoreComponent] = []
    strengths: list[MetricHighlight] = []
    risks: list[MetricHighlight] = []
    warnings: list[str] = []
    peer_outliers: list[PeerOutlier] = []
    run: RunRef | None = None


class ComparisonResponse(BaseModel):
    scoring_model: ScoringModelRef
    areas: list[AreaScoreResult] = Field(description="In request order")


class PreviewResponse(ComparisonResponse):
    temporary: Literal[True] = True


# ---------------------------------------------------------------- runs and models


class AnalysisRunOut(BaseModel):
    id: uuid.UUID
    service_area_id: uuid.UUID
    pipeline_version: str
    parameters: dict[str, Any]
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    source_metadata: dict[str, Any]


class AnalysisRunPage(BaseModel):
    items: list[AnalysisRunOut]
    total: int
    limit: int
    offset: int


class ScoringModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    weights: dict[str, float]
    normalization_version: str
    is_default: bool
    created_at: datetime


class ScoringModelList(BaseModel):
    items: list[ScoringModelOut]
