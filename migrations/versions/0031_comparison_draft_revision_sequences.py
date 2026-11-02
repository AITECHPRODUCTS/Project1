"""Add atomic workspace-scoped comparison draft revision counters."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0031_comparison_draft_revision_sequences"
down_revision = "0030_resend_email_delivery_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comparison_draft_revision_sequences",
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("root_asset_id", sa.String(length=36), sa.ForeignKey("content_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("next_revision_number", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "workspace_id", "root_asset_id",
            name="uq_comparison_draft_revision_sequence_workspace_root",
        ),
    )
    op.create_index(
        "ix_comparison_draft_revision_sequences_workspace_id",
        "comparison_draft_revision_sequences",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_comparison_draft_revision_sequences_workspace_id",
        table_name="comparison_draft_revision_sequences",
    )
    op.drop_table("comparison_draft_revision_sequences")
