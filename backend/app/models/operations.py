"""Strictly synthetic operational tables; no records can claim to be real fleet data."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now_column


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id"), nullable=False
    )
    scenario_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    generator_version: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    simulated_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = now_column()
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("is_synthetic = true", name="synthetic_only"),
        Index("ix_simulation_runs_analysis_created", "analysis_run_id", "created_at"),
    )


class RouteEvent(Base):
    __tablename__ = "route_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    intervention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("is_synthetic = true", name="synthetic_only"),
        CheckConstraint("distance_km >= 0 AND duration_minutes > 0", name="positive_route_values"),
        CheckConstraint("intervention_count >= 0", name="nonnegative_interventions"),
        CheckConstraint("ended_at >= started_at", name="ordered_route_times"),
    )


class OperationalIssue(Base):
    __tablename__ = "operational_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("is_synthetic = true", name="synthetic_only"),
        CheckConstraint("severity IN ('info', 'warning', 'critical')", name="valid_severity"),
        CheckConstraint("status IN ('open', 'resolved')", name="valid_status"),
        CheckConstraint(
            "(status = 'open' AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_at >= created_at)",
            name="consistent_resolution",
        ),
    )
