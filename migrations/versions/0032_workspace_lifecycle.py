"""Add workspace lifecycle and suspension evidence."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0032_workspace_lifecycle"
down_revision = "0031_comparison_draft_revision_sequences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("lifecycle_state", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("workspaces", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workspaces", sa.Column("suspended_by", sa.String(length=320), nullable=True))
    op.add_column("workspaces", sa.Column("suspension_reason", sa.Text(), nullable=True))
    op.create_index("ix_workspaces_lifecycle_state", "workspaces", ["lifecycle_state"])


def downgrade() -> None:
    op.drop_index("ix_workspaces_lifecycle_state", table_name="workspaces")
    op.drop_column("workspaces", "suspension_reason")
    op.drop_column("workspaces", "suspended_by")
    op.drop_column("workspaces", "suspended_at")
    op.drop_column("workspaces", "lifecycle_state")
