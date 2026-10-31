"""Add strictly synthetic operational scenarios.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_run_id", sa.UUID(), nullable=False),
        sa.Column("scenario_key", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("generator_version", sa.String(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("simulated_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.CheckConstraint("is_synthetic = true", name=op.f("ck_simulation_runs_synthetic_only")),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_simulation_runs_analysis_run_id_analysis_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_runs")),
        sa.UniqueConstraint("scenario_key", name=op.f("uq_simulation_runs_scenario_key")),
    )
    op.create_index(
        "ix_simulation_runs_analysis_created",
        "simulation_runs",
        ["analysis_run_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "operational_issues",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("simulation_run_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "(status = 'open' AND resolved_at IS NULL) OR (status = 'resolved' AND resolved_at IS NOT NULL AND resolved_at >= created_at)",
            name=op.f("ck_operational_issues_consistent_resolution"),
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name=op.f("ck_operational_issues_valid_severity"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')", name=op.f("ck_operational_issues_valid_status")
        ),
        sa.CheckConstraint(
            "is_synthetic = true", name=op.f("ck_operational_issues_synthetic_only")
        ),
        sa.ForeignKeyConstraint(
            ["simulation_run_id"],
            ["simulation_runs.id"],
            name=op.f("fk_operational_issues_simulation_run_id_simulation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operational_issues")),
    )
    op.create_index(
        op.f("ix_operational_issues_simulation_run_id"),
        "operational_issues",
        ["simulation_run_id"],
        unique=False,
    )
    op.create_table(
        "route_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("simulation_run_id", sa.UUID(), nullable=False),
        sa.Column("route_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("duration_minutes", sa.Float(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("intervention_count", sa.Integer(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "distance_km >= 0 AND duration_minutes > 0",
            name=op.f("ck_route_events_positive_route_values"),
        ),
        sa.CheckConstraint(
            "ended_at >= started_at", name=op.f("ck_route_events_ordered_route_times")
        ),
        sa.CheckConstraint(
            "intervention_count >= 0", name=op.f("ck_route_events_nonnegative_interventions")
        ),
        sa.CheckConstraint("is_synthetic = true", name=op.f("ck_route_events_synthetic_only")),
        sa.ForeignKeyConstraint(
            ["simulation_run_id"],
            ["simulation_runs.id"],
            name=op.f("fk_route_events_simulation_run_id_simulation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_route_events")),
    )
    op.create_index(
        op.f("ix_route_events_simulation_run_id"),
        "route_events",
        ["simulation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("route_events")
    op.drop_table("operational_issues")
    op.drop_table("simulation_runs")
