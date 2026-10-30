"""Persist PII-minimized ClickBank affiliate order observations."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0036_provider_order_observations"
down_revision = "0035_provider_account_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_order_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), sa.ForeignKey("provider_account_connections.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("account_nickname", sa.String(length=100), nullable=False),
        sa.Column("receipt", sa.String(length=80), nullable=False),
        sa.Column("transaction_time", sa.String(length=80), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("vendor_nickname", sa.String(length=100), nullable=True),
        sa.Column("affiliate_nickname", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("item_number", sa.String(length=100), nullable=True),
        sa.Column("line_item_type", sa.String(length=80), nullable=True),
        sa.Column("product_title", sa.String(length=500), nullable=True),
        sa.Column("account_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("customer_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("line_item_status", sa.String(length=80), nullable=True),
        sa.Column("recurring", sa.Boolean(), nullable=True),
        sa.Column("shippable", sa.Boolean(), nullable=True),
        sa.Column("evidence_status", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("role = 'AFFILIATE'", name="ck_provider_order_observations_affiliate_role"),
        sa.CheckConstraint("evidence_status IN ('provider_reported_unreconciled')", name="ck_provider_order_observations_evidence_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "provider_id", "event_key", "source_fingerprint", name="uq_provider_order_observation_workspace_source"),
    )
    op.create_index("ix_provider_order_observations_workspace_connection_observed", "provider_order_observations", ["workspace_id", "connection_id", "observed_at"])
    op.create_index("ix_provider_order_observations_workspace_account_time", "provider_order_observations", ["workspace_id", "account_nickname", "transaction_time"])
    op.create_index("ix_provider_order_observations_connection_id", "provider_order_observations", ["connection_id"])
    op.create_index("ix_provider_order_observations_provider_id", "provider_order_observations", ["provider_id"])
    op.create_index("ix_provider_order_observations_account_nickname", "provider_order_observations", ["account_nickname"])
    op.create_index("ix_provider_order_observations_receipt", "provider_order_observations", ["receipt"])
    op.create_index("ix_provider_order_observations_transaction_time", "provider_order_observations", ["transaction_time"])
    op.create_index("ix_provider_order_observations_transaction_type", "provider_order_observations", ["transaction_type"])


def downgrade() -> None:
    op.drop_index("ix_provider_order_observations_transaction_type", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_transaction_time", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_receipt", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_account_nickname", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_provider_id", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_connection_id", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_workspace_account_time", table_name="provider_order_observations")
    op.drop_index("ix_provider_order_observations_workspace_connection_observed", table_name="provider_order_observations")
    op.drop_table("provider_order_observations")
