"""ORM models. docs/data-model.md is the authoritative schema description."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now_column


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class ServiceArea(Base):
    __tablename__ = "service_areas"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    boundary: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = now_column()

    __table_args__ = (Index("ix_service_areas_boundary", "boundary", postgresql_using="gist"),)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    service_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_areas.id"), nullable=False, index=True
    )
    pipeline_version: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="status_valid"),
    )


class H3Cell(Base):
    __tablename__ = "h3_cells"

    h3_index: Mapped[str] = mapped_column(String, primary_key=True)
    resolution: Mapped[int] = mapped_column(Integer, nullable=False)
    boundary: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False
    )
    centroid: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )

    __table_args__ = (
        CheckConstraint("resolution BETWEEN 0 AND 15", name="resolution_range"),
        Index("ix_h3_cells_boundary", "boundary", postgresql_using="gist"),
    )


class AnalysisRunCell(Base):
    __tablename__ = "analysis_run_cells"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True
    )
    h3_index: Mapped[str] = mapped_column(ForeignKey("h3_cells.h3_index"), primary_key=True)
    overlap_ratio: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint("overlap_ratio BETWEEN 0 AND 1", name="overlap_ratio_range"),
        Index("ix_analysis_run_cells_h3_index", "h3_index"),
    )


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, nullable=False)
    normalization_method: Mapped[str] = mapped_column(String, nullable=False)
    ref_min: Mapped[float | None] = mapped_column(Float)
    ref_max: Mapped[float | None] = mapped_column(Float)
    version: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "ref_min IS NULL OR ref_max IS NULL OR ref_min <> ref_max", name="ref_range_nonempty"
        ),
    )


def _range_checks() -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint(
            "normalized_value IS NULL OR normalized_value BETWEEN 0 AND 1",
            name="normalized_value_range",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
    )


class CellMetric(Base):
    __tablename__ = "cell_metrics"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    h3_index: Mapped[str] = mapped_column(String, primary_key=True)
    metric_key: Mapped[str] = mapped_column(ForeignKey("metric_definitions.key"), primary_key=True)
    raw_value: Mapped[float | None] = mapped_column(Float)
    normalized_value: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

    __table_args__ = (
        ForeignKeyConstraint(
            ["analysis_run_id", "h3_index"],
            ["analysis_run_cells.analysis_run_id", "analysis_run_cells.h3_index"],
            ondelete="CASCADE",
            name="fk_cell_metrics_run_cell",
        ),
        *_range_checks(),
    )


class AreaMetric(Base):
    __tablename__ = "area_metrics"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True
    )
    metric_key: Mapped[str] = mapped_column(ForeignKey("metric_definitions.key"), primary_key=True)
    raw_value: Mapped[float | None] = mapped_column(Float)
    normalized_value: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = _range_checks()


class ScoringModel(Base):
    __tablename__ = "scoring_models"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalization_version: Mapped[str] = mapped_column(String, nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = now_column()

    __table_args__ = (
        UniqueConstraint("name", "version"),
        Index(
            "uq_scoring_models_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )


class AreaScore(Base):
    __tablename__ = "area_scores"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True
    )
    scoring_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scoring_models.id"), primary_key=True
    )
    score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    component_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
    )


class DataQualityFinding(Base):
    __tablename__ = "data_quality_findings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_key: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    affected_fraction: Mapped[float | None] = mapped_column(Float)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

    __table_args__ = (
        CheckConstraint("severity IN ('info', 'warning', 'critical')", name="severity_valid"),
        CheckConstraint(
            "affected_fraction IS NULL OR affected_fraction BETWEEN 0 AND 1",
            name="affected_fraction_range",
        ),
    )
