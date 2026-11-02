"""Persist reported ad performance observations and evidence status."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_ad_performance_observations"
down_revision = "0003_ad_campaign_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_performance_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("campaign_plan_id", sa.String(length=36), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("creative_id", sa.String(length=180), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference_url", sa.Text(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("conversions", sa.Integer(), nullable=False),
        sa.Column("spend_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("commission_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("evidence_status", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_ad_performance_observations_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_plan_id"],
            ["ad_campaign_plans.id"],
            name="fk_ad_perf_obs_campaign_plan",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_performance_observations_workspace_id", "ad_performance_observations", ["workspace_id"])
    op.create_index("ix_ad_performance_observations_campaign_plan_id", "ad_performance_observations", ["campaign_plan_id"])
    op.create_index("ix_ad_performance_observations_platform", "ad_performance_observations", ["platform"])
    op.create_index("ix_ad_performance_observations_creative_id", "ad_performance_observations", ["creative_id"])
    op.create_index("ix_ad_performance_observations_source_type", "ad_performance_observations", ["source_type"])
    op.create_index("ix_ad_performance_observations_evidence_status", "ad_performance_observations", ["evidence_status"])
    op.create_index("ix_ad_performance_observations_observed_at", "ad_performance_observations", ["observed_at"])
    op.create_index("ix_ad_performance_observations_created_at", "ad_performance_observations", ["created_at"])
    op.create_index(
        "ix_ad_performance_observations_workspace_plan_creative",
        "ad_performance_observations",
        ["workspace_id", "campaign_plan_id", "creative_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ad_performance_observations_workspace_plan_creative", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_created_at", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_observed_at", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_evidence_status", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_source_type", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_creative_id", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_platform", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_campaign_plan_id", table_name="ad_performance_observations")
    op.drop_index("ix_ad_performance_observations_workspace_id", table_name="ad_performance_observations")
    op.drop_table("ad_performance_observations")
