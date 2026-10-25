"""initial domain schema

Revision ID: 0001
Revises:
Create Date: 2026-10-25 12:02:09.899966

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_geospatial_table(
        "h3_cells",
        sa.Column("h3_index", sa.String(), nullable=False),
        sa.Column("resolution", sa.Integer(), nullable=False),
        sa.Column(
            "boundary",
            Geometry(
                geometry_type="POLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "centroid",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resolution BETWEEN 0 AND 15", name=op.f("ck_h3_cells_resolution_range")
        ),
        sa.PrimaryKeyConstraint("h3_index", name=op.f("pk_h3_cells")),
    )
    op.create_geospatial_index(
        "ix_h3_cells_boundary",
        "h3_cells",
        ["boundary"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_table(
        "metric_definitions",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("higher_is_better", sa.Boolean(), nullable=False),
        sa.Column("normalization_method", sa.String(), nullable=False),
        sa.Column("ref_min", sa.Float(), nullable=True),
        sa.Column("ref_max", sa.Float(), nullable=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.CheckConstraint(
            "ref_min IS NULL OR ref_max IS NULL OR ref_min <> ref_max",
            name=op.f("ck_metric_definitions_ref_range_nonempty"),
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_metric_definitions")),
    )
    op.create_table(
        "scoring_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalization_version", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_models")),
        sa.UniqueConstraint("name", "version", name=op.f("uq_scoring_models_name")),
    )
    op.create_index(
        "uq_scoring_models_single_default",
        "scoring_models",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_geospatial_table(
        "service_areas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column(
            "boundary",
            Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_areas")),
        sa.UniqueConstraint("slug", name=op.f("uq_service_areas_slug")),
    )
    op.create_geospatial_index(
        "ix_service_areas_boundary",
        "service_areas",
        ["boundary"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("service_area_id", sa.UUID(), nullable=False),
        sa.Column("pipeline_version", sa.String(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_analysis_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["service_area_id"],
            ["service_areas.id"],
            name=op.f("fk_analysis_runs_service_area_id_service_areas"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(
        op.f("ix_analysis_runs_service_area_id"), "analysis_runs", ["service_area_id"], unique=False
    )
    op.create_table(
        "analysis_run_cells",
        sa.Column("analysis_run_id", sa.UUID(), nullable=False),
        sa.Column("h3_index", sa.String(), nullable=False),
        sa.Column("overlap_ratio", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "overlap_ratio BETWEEN 0 AND 1", name=op.f("ck_analysis_run_cells_overlap_ratio_range")
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_run_cells_analysis_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["h3_index"],
            ["h3_cells.h3_index"],
            name=op.f("fk_analysis_run_cells_h3_index_h3_cells"),
        ),
        sa.PrimaryKeyConstraint("analysis_run_id", "h3_index", name=op.f("pk_analysis_run_cells")),
    )
    op.create_index(
        "ix_analysis_run_cells_h3_index", "analysis_run_cells", ["h3_index"], unique=False
    )
    op.create_table(
        "area_metrics",
        sa.Column("analysis_run_id", sa.UUID(), nullable=False),
        sa.Column("metric_key", sa.String(), nullable=False),
        sa.Column("raw_value", sa.Float(), nullable=True),
        sa.Column("normalized_value", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name=op.f("ck_area_metrics_confidence_range"),
        ),
        sa.CheckConstraint(
            "normalized_value IS NULL OR normalized_value BETWEEN 0 AND 1",
            name=op.f("ck_area_metrics_normalized_value_range"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_area_metrics_analysis_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["metric_key"],
            ["metric_definitions.key"],
            name=op.f("fk_area_metrics_metric_key_metric_definitions"),
        ),
        sa.PrimaryKeyConstraint("analysis_run_id", "metric_key", name=op.f("pk_area_metrics")),
    )
    op.create_table(
        "area_scores",
        sa.Column("analysis_run_id", sa.UUID(), nullable=False),
        sa.Column("scoring_model_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("component_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name=op.f("ck_area_scores_confidence_range")
        ),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name=op.f("ck_area_scores_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_area_scores_analysis_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scoring_model_id"],
            ["scoring_models.id"],
            name=op.f("fk_area_scores_scoring_model_id_scoring_models"),
        ),
        sa.PrimaryKeyConstraint("analysis_run_id", "scoring_model_id", name=op.f("pk_area_scores")),
    )
    op.create_table(
        "data_quality_findings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_run_id", sa.UUID(), nullable=False),
        sa.Column("rule_key", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("affected_fraction", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name=op.f("ck_data_quality_findings_severity_valid"),
        ),
        sa.CheckConstraint(
            "affected_fraction IS NULL OR affected_fraction BETWEEN 0 AND 1",
            name=op.f("ck_data_quality_findings_affected_fraction_range"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_data_quality_findings_analysis_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_quality_findings")),
    )
    op.create_index(
        op.f("ix_data_quality_findings_analysis_run_id"),
        "data_quality_findings",
        ["analysis_run_id"],
        unique=False,
    )
    op.create_table(
        "cell_metrics",
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("h3_index", sa.String(), nullable=False),
        sa.Column("metric_key", sa.String(), nullable=False),
        sa.Column("raw_value", sa.Float(), nullable=True),
        sa.Column("normalized_value", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name=op.f("ck_cell_metrics_confidence_range"),
        ),
        sa.CheckConstraint(
            "normalized_value IS NULL OR normalized_value BETWEEN 0 AND 1",
            name=op.f("ck_cell_metrics_normalized_value_range"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id", "h3_index"],
            ["analysis_run_cells.analysis_run_id", "analysis_run_cells.h3_index"],
            name="fk_cell_metrics_run_cell",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["metric_key"],
            ["metric_definitions.key"],
            name=op.f("fk_cell_metrics_metric_key_metric_definitions"),
        ),
        sa.PrimaryKeyConstraint(
            "analysis_run_id", "h3_index", "metric_key", name=op.f("pk_cell_metrics")
        ),
    )


def downgrade() -> None:
    """Downgrade schema (the postgis extension is deliberately left installed)."""
    op.drop_table("cell_metrics")
    op.drop_index(
        op.f("ix_data_quality_findings_analysis_run_id"), table_name="data_quality_findings"
    )
    op.drop_table("data_quality_findings")
    op.drop_table("area_scores")
    op.drop_table("area_metrics")
    op.drop_index("ix_analysis_run_cells_h3_index", table_name="analysis_run_cells")
    op.drop_table("analysis_run_cells")
    op.drop_index(op.f("ix_analysis_runs_service_area_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_geospatial_index(
        "ix_service_areas_boundary",
        table_name="service_areas",
        postgresql_using="gist",
        column_name="boundary",
    )
    op.drop_geospatial_table("service_areas")
    op.drop_index(
        "uq_scoring_models_single_default",
        table_name="scoring_models",
        postgresql_where=sa.text("is_default"),
    )
    op.drop_table("scoring_models")
    op.drop_table("metric_definitions")
    op.drop_geospatial_index(
        "ix_h3_cells_boundary",
        table_name="h3_cells",
        postgresql_using="gist",
        column_name="boundary",
    )
    op.drop_geospatial_table("h3_cells")
