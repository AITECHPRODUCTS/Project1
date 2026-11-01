"""Add merchant signed webhooks, affiliate promotion links and program payout terms."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0042_merchant_partner_integrations"
down_revision = "0041_platform_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("merchant_offers") as batch:
        batch.add_column(sa.Column("cookie_days", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("attribution_window_days", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("refund_hold_days", sa.Integer(), nullable=False, server_default="15"))
        batch.add_column(sa.Column("minimum_payout_amount", sa.Numeric(12, 2), nullable=False, server_default="20.00"))
        batch.add_column(sa.Column("payout_schedule", sa.String(length=40), nullable=False, server_default="monthly"))

    op.create_table(
        "merchant_webhook_integrations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_offer_id", sa.String(length=36), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("integration_type", sa.String(length=40), nullable=False, server_default="signed_webhook"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending_authorization"),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("secret_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending_authorization', 'connected_write', 'degraded', 'disabled')", name="ck_merchant_webhook_integration_status"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_offer_id"], ["merchant_offers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "merchant_offer_id", name="uq_merchant_webhook_offer"),
    )
    op.create_index("ix_merchant_webhook_integrations_workspace_id", "merchant_webhook_integrations", ["workspace_id"])
    op.create_index("ix_merchant_webhook_integrations_merchant_offer_id", "merchant_webhook_integrations", ["merchant_offer_id"])
    op.create_index("ix_merchant_webhook_workspace_status", "merchant_webhook_integrations", ["workspace_id", "status"])

    op.create_table(
        "affiliate_program_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_workspace_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_offer_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'suspended', 'disabled')", name="ck_affiliate_program_link_status"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_offer_id"], ["merchant_offers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["marketplace_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "application_id", name="uq_affiliate_program_link_application"),
        sa.UniqueConstraint("campaign_id", name="uq_affiliate_program_link_campaign"),
    )
    op.create_index("ix_affiliate_program_links_workspace_id", "affiliate_program_links", ["workspace_id"])
    op.create_index("ix_affiliate_program_links_merchant_workspace_id", "affiliate_program_links", ["merchant_workspace_id"])
    op.create_index("ix_affiliate_program_links_merchant_offer_id", "affiliate_program_links", ["merchant_offer_id"])
    op.create_index("ix_affiliate_program_links_application_id", "affiliate_program_links", ["application_id"])
    op.create_index("ix_affiliate_program_links_campaign_id", "affiliate_program_links", ["campaign_id"])
    op.create_index("ix_affiliate_program_links_workspace_status", "affiliate_program_links", ["workspace_id", "status"])
    op.create_index("ix_affiliate_program_links_merchant_offer", "affiliate_program_links", ["merchant_workspace_id", "merchant_offer_id"])

    op.create_table(
        "merchant_webhook_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("conversion_id", sa.String(length=36), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["integration_id"], ["merchant_webhook_integrations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "provider_event_id", name="uq_merchant_webhook_event"),
    )
    op.create_index("ix_merchant_webhook_receipts_integration_received", "merchant_webhook_receipts", ["integration_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_merchant_webhook_receipts_integration_received", table_name="merchant_webhook_receipts")
    op.drop_table("merchant_webhook_receipts")
    op.drop_index("ix_affiliate_program_links_merchant_offer", table_name="affiliate_program_links")
    op.drop_index("ix_affiliate_program_links_workspace_status", table_name="affiliate_program_links")
    op.drop_index("ix_affiliate_program_links_campaign_id", table_name="affiliate_program_links")
    op.drop_index("ix_affiliate_program_links_application_id", table_name="affiliate_program_links")
    op.drop_index("ix_affiliate_program_links_merchant_offer_id", table_name="affiliate_program_links")
    op.drop_index("ix_affiliate_program_links_merchant_workspace_id", table_name="affiliate_program_links")
    op.drop_index("ix_affiliate_program_links_workspace_id", table_name="affiliate_program_links")
    op.drop_table("affiliate_program_links")
    op.drop_index("ix_merchant_webhook_workspace_status", table_name="merchant_webhook_integrations")
    op.drop_index("ix_merchant_webhook_integrations_merchant_offer_id", table_name="merchant_webhook_integrations")
    op.drop_index("ix_merchant_webhook_integrations_workspace_id", table_name="merchant_webhook_integrations")
    op.drop_table("merchant_webhook_integrations")
    with op.batch_alter_table("merchant_offers") as batch:
        batch.drop_column("payout_schedule")
        batch.drop_column("minimum_payout_amount")
        batch.drop_column("refund_hold_days")
        batch.drop_column("attribution_window_days")
        batch.drop_column("cookie_days")
