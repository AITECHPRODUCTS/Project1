"""Persist workspace-scoped public evidence snapshots for offer qualification."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0039_offer_evidence_snapshots"
down_revision = "0038_provider_catalog_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offer_evidence_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("offer_id", sa.String(length=36), sa.ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_host", sa.String(length=253), nullable=False),
        sa.Column("title", sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("excerpt", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("response_sha256", sa.String(length=64), nullable=True),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=120), server_default=sa.text("''"), nullable=False),
        sa.Column("fetch_status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "fetch_status IN ('fetched', 'fetch_failed')",
            name="ck_offer_evidence_snapshot_fetch_status",
        ),
        sa.CheckConstraint("workspace_id IS NOT NULL", name="ck_offer_evidence_snapshot_workspace_required"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offer_evidence_snapshots_workspace_id", "offer_evidence_snapshots", ["workspace_id"])
    op.create_index("ix_offer_evidence_snapshots_offer_id", "offer_evidence_snapshots", ["offer_id"])
    op.create_index(
        "ix_offer_evidence_workspace_offer_fetched",
        "offer_evidence_snapshots",
        ["workspace_id", "offer_id", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_offer_evidence_workspace_offer_fetched", table_name="offer_evidence_snapshots")
    op.drop_index("ix_offer_evidence_snapshots_offer_id", table_name="offer_evidence_snapshots")
    op.drop_index("ix_offer_evidence_snapshots_workspace_id", table_name="offer_evidence_snapshots")
    op.drop_table("offer_evidence_snapshots")
