"""Persist ad budget caps, verified-evidence evaluation and a stop latch."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_ad_budget_guardrails"
down_revision = "0015_marketplace_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_budget_guardrails",
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_plan_id", sa.String(length=36), nullable=False),
        sa.Column("daily_spend_cap_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("campaign_spend_cap_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("minimum_roas", sa.Numeric(8, 4), nullable=False),
        sa.Column("maximum_cpa_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("minimum_verified_impressions", sa.Integer(), nullable=False),
        sa.Column("minimum_verified_clicks", sa.Integer(), nullable=False),
        sa.Column("minimum_verified_conversions", sa.Integer(), nullable=False),
        sa.Column("kill_switch_engaged", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("stop_latched", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_evaluation_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("updated_by", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_ad_budget_guardrails_workspace_id_workspaces", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["campaign_plan_id"], ["ad_campaign_plans.id"], name="fk_ad_budget_guardrails_campaign_plan", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "campaign_plan_id", name="uq_ad_budget_guardrails_workspace_plan"),
    )
    op.create_index("ix_ad_budget_guardrails_workspace_id", "ad_budget_guardrails", ["workspace_id"])
    op.create_index("ix_ad_budget_guardrails_campaign_plan_id", "ad_budget_guardrails", ["campaign_plan_id"])
    op.create_index("ix_ad_budget_guardrails_workspace_stop", "ad_budget_guardrails", ["workspace_id", "kill_switch_engaged", "stop_latched"])


def downgrade() -> None:
    op.drop_index("ix_ad_budget_guardrails_workspace_stop", table_name="ad_budget_guardrails")
    op.drop_index("ix_ad_budget_guardrails_campaign_plan_id", table_name="ad_budget_guardrails")
    op.drop_index("ix_ad_budget_guardrails_workspace_id", table_name="ad_budget_guardrails")
    op.drop_table("ad_budget_guardrails")
