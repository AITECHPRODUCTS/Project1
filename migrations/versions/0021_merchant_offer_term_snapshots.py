"""Persist immutable, evidence-labelled merchant offer term snapshots."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0021_merchant_offer_term_snapshots"
down_revision = "0020_distribution_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_offer_term_snapshots",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("merchant_offer_id", sa.String(length=36), nullable=False),
        sa.Column("terms_version", sa.String(length=120), nullable=False),
        sa.Column("commission_type", sa.String(length=40), nullable=False),
        sa.Column("commission_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("commission_currency", sa.String(length=3), nullable=False),
        sa.Column("cookie_days", sa.Integer(), nullable=True),
        sa.Column("attribution_window_days", sa.Integer(), nullable=True),
        sa.Column("allowed_regions_json", sa.JSON(), nullable=False),
        sa.Column("restricted_traffic_sources_json", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("evidence_excerpt", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("terms_sha256", sa.String(length=64), nullable=False),
        sa.Column("change_status", sa.String(length=40), nullable=False),
        sa.Column("changed_fields_json", sa.JSON(), nullable=False),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("provenance_status", sa.String(length=40), nullable=False),
        sa.Column("provider_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_content_fetched", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_offer_id"], ["merchant_offers.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_merchant_offer_term_snapshots_workspace_id",
        "merchant_offer_term_snapshots",
        ["workspace_id"],
    )
    op.create_index(
        "ix_merchant_offer_terms_workspace_offer_captured",
        "merchant_offer_term_snapshots",
        ["workspace_id", "merchant_offer_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_offer_terms_workspace_offer_captured", table_name="merchant_offer_term_snapshots")
    op.drop_index("ix_merchant_offer_term_snapshots_workspace_id", table_name="merchant_offer_term_snapshots")
    op.drop_table("merchant_offer_term_snapshots")
