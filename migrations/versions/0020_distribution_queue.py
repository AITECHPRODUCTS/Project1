"""Persist a workspace-scoped review and scheduling queue for distribution content."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0020_distribution_queue"
down_revision = "0019_governed_skill_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "distribution_queue_items",
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("source_asset_id", sa.String(length=36), nullable=False),
        sa.Column("source_asset_type", sa.String(length=100), nullable=False),
        sa.Column("content_title", sa.String(length=500), nullable=False),
        sa.Column("content_body", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_urls_json", sa.JSON(), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("target_jurisdictions_json", sa.JSON(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("cancelled_by", sa.String(length=320), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["content_assets.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("workspace_id", "idempotency_key", name="uq_distribution_queue_workspace_key"),
    )
    op.create_index("ix_distribution_queue_items_workspace_id", "distribution_queue_items", ["workspace_id"])
    op.create_index("ix_distribution_queue_items_source_asset_id", "distribution_queue_items", ["source_asset_id"])
    op.create_index("ix_distribution_queue_workspace_status_schedule", "distribution_queue_items", ["workspace_id", "status", "scheduled_at"])
    op.create_index("ix_distribution_queue_workspace_created", "distribution_queue_items", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_distribution_queue_workspace_created", table_name="distribution_queue_items")
    op.drop_index("ix_distribution_queue_workspace_status_schedule", table_name="distribution_queue_items")
    op.drop_index("ix_distribution_queue_items_source_asset_id", table_name="distribution_queue_items")
    op.drop_index("ix_distribution_queue_items_workspace_id", table_name="distribution_queue_items")
    op.drop_table("distribution_queue_items")
