"""Add workspace-scoped merchant offer review lifecycle."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0014_merchant_offers"
down_revision = "0013_program_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_offers",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=160), nullable=False),
        sa.Column("commission_type", sa.String(length=40), nullable=False),
        sa.Column("commission_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("commission_currency", sa.String(length=3), nullable=False),
        sa.Column("terms_version", sa.String(length=120), nullable=False),
        sa.Column("commission_terms_url", sa.Text(), nullable=False),
        sa.Column("seller_authorization_url", sa.Text(), nullable=False),
        sa.Column("allowed_regions_json", sa.JSON(), nullable=False),
        sa.Column("restricted_traffic_sources_json", sa.JSON(), nullable=False),
        sa.Column("affiliate_disclosure", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("terms_verified", sa.Boolean(), nullable=False),
        sa.Column("seller_authorization_verified", sa.Boolean(), nullable=False),
        sa.Column("activation_allowed", sa.Boolean(), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affiliate_network_approval_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_merchant_offers_workspace_id_workspaces", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_offers_workspace_id", "merchant_offers", ["workspace_id"])
    op.create_index("ix_merchant_offers_category", "merchant_offers", ["category"])
    op.create_index("ix_merchant_offers_status", "merchant_offers", ["status"])
    op.create_index(
        "ix_merchant_offers_workspace_status_created",
        "merchant_offers", ["workspace_id", "status", "created_at"]
    )
    op.create_index("ix_merchant_offers_workspace_name", "merchant_offers", ["workspace_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_merchant_offers_workspace_name", table_name="merchant_offers")
    op.drop_index("ix_merchant_offers_workspace_status_created", table_name="merchant_offers")
    op.drop_index("ix_merchant_offers_status", table_name="merchant_offers")
    op.drop_index("ix_merchant_offers_category", table_name="merchant_offers")
    op.drop_index("ix_merchant_offers_workspace_id", table_name="merchant_offers")
    op.drop_table("merchant_offers")
