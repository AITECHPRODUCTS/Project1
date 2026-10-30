"""Persist workspace-scoped provider product and offer snapshots."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0038_provider_catalog_observations"
down_revision = "0037_provider_order_click_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_catalog_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("connection_id", sa.String(length=36), sa.ForeignKey("provider_account_connections.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("observation_type", sa.String(length=16), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("brand", sa.String(length=200), nullable=True),
        sa.Column("provider_url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("mrp_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=True),
        sa.Column("availability_status", sa.String(length=40), nullable=True),
        sa.Column("discount_percentage", sa.Numeric(6, 3), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_endpoint", sa.String(length=160), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("observation_type IN ('product', 'offer')", name="ck_provider_catalog_observations_type"),
        sa.CheckConstraint("workspace_id IS NOT NULL", name="ck_provider_catalog_observations_workspace_required"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "connection_id", "provider_id", "observation_type", "external_id",
            name="uq_provider_catalog_observation_workspace_source",
        ),
    )
    op.create_index("ix_provider_catalog_observations_workspace_id", "provider_catalog_observations", ["workspace_id"])
    op.create_index("ix_provider_catalog_observations_connection_id", "provider_catalog_observations", ["connection_id"])
    op.create_index("ix_provider_catalog_observations_provider_id", "provider_catalog_observations", ["provider_id"])
    op.create_index(
        "ix_provider_catalog_observations_workspace_connection_seen",
        "provider_catalog_observations", ["workspace_id", "connection_id", "observed_at"],
    )
    op.create_index(
        "ix_provider_catalog_observations_workspace_category",
        "provider_catalog_observations", ["workspace_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_catalog_observations_workspace_category", table_name="provider_catalog_observations")
    op.drop_index("ix_provider_catalog_observations_workspace_connection_seen", table_name="provider_catalog_observations")
    op.drop_index("ix_provider_catalog_observations_provider_id", table_name="provider_catalog_observations")
    op.drop_index("ix_provider_catalog_observations_connection_id", table_name="provider_catalog_observations")
    op.drop_index("ix_provider_catalog_observations_workspace_id", table_name="provider_catalog_observations")
    op.drop_table("provider_catalog_observations")
