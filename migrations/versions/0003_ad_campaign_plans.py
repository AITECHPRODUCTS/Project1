"""Persist tenant-scoped ad campaign plans and creative variants."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_ad_campaign_plans"
down_revision = "0002_workspace_tenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_campaign_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("campaign_name", sa.String(length=160), nullable=False),
        sa.Column("niche", sa.String(length=200), nullable=False),
        sa.Column("audience", sa.String(length=400), nullable=False),
        sa.Column("region", sa.String(length=120), nullable=False),
        sa.Column("objective", sa.String(length=40), nullable=False),
        sa.Column("platforms_json", sa.JSON(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("daily_budget_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_ad_campaign_plans_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_campaign_plans_workspace_id", "ad_campaign_plans", ["workspace_id"])
    op.create_index("ix_ad_campaign_plans_niche", "ad_campaign_plans", ["niche"])
    op.create_index("ix_ad_campaign_plans_status", "ad_campaign_plans", ["status"])
    op.create_index(
        "ix_ad_campaign_plans_workspace_status",
        "ad_campaign_plans",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ad_campaign_plans_workspace_status", table_name="ad_campaign_plans")
    op.drop_index("ix_ad_campaign_plans_status", table_name="ad_campaign_plans")
    op.drop_index("ix_ad_campaign_plans_niche", table_name="ad_campaign_plans")
    op.drop_index("ix_ad_campaign_plans_workspace_id", table_name="ad_campaign_plans")
    op.drop_table("ad_campaign_plans")
