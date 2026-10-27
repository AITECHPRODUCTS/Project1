"""Add internal marketplace listings and cross-workspace publisher applications."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0015_marketplace_applications"
down_revision = "0014_merchant_offers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_offers",
        sa.Column("marketplace_listed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_merchant_offers_marketplace_listed", "merchant_offers", ["marketplace_listed"])
    op.create_table(
        "marketplace_applications",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_workspace_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_offer_id", sa.String(length=36), nullable=False),
        sa.Column("applicant_email", sa.String(length=320), nullable=False),
        sa.Column("publisher_website_url", sa.Text(), nullable=False),
        sa.Column("audience_description", sa.Text(), nullable=False),
        sa.Column("traffic_sources_json", sa.JSON(), nullable=False),
        sa.Column("intended_regions_json", sa.JSON(), nullable=False),
        sa.Column("promotion_plan", sa.Text(), nullable=False),
        sa.Column("compliance_answers_json", sa.JSON(), nullable=False),
        sa.Column("terms_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_marketplace_applications_publisher_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_workspace_id"], ["workspaces.id"], name="fk_marketplace_applications_merchant_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_offer_id"], ["merchant_offers.id"], name="fk_marketplace_applications_merchant_offer", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "merchant_offer_id", name="uq_marketplace_application_publisher_offer"),
    )
    op.create_index("ix_marketplace_applications_workspace_id", "marketplace_applications", ["workspace_id"])
    op.create_index("ix_marketplace_applications_merchant_workspace_id", "marketplace_applications", ["merchant_workspace_id"])
    op.create_index("ix_marketplace_applications_merchant_offer_id", "marketplace_applications", ["merchant_offer_id"])
    op.create_index("ix_marketplace_applications_status", "marketplace_applications", ["status"])
    op.create_index("ix_marketplace_apps_workspace_status_created", "marketplace_applications", ["workspace_id", "status", "created_at"])
    op.create_index("ix_marketplace_apps_merchant_status_created", "marketplace_applications", ["merchant_workspace_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_apps_merchant_status_created", table_name="marketplace_applications")
    op.drop_index("ix_marketplace_apps_workspace_status_created", table_name="marketplace_applications")
    op.drop_index("ix_marketplace_applications_status", table_name="marketplace_applications")
    op.drop_index("ix_marketplace_applications_merchant_offer_id", table_name="marketplace_applications")
    op.drop_index("ix_marketplace_applications_merchant_workspace_id", table_name="marketplace_applications")
    op.drop_index("ix_marketplace_applications_workspace_id", table_name="marketplace_applications")
    op.drop_table("marketplace_applications")
    op.drop_index("ix_merchant_offers_marketplace_listed", table_name="merchant_offers")
    op.drop_column("merchant_offers", "marketplace_listed")
