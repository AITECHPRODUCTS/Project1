"""Add expiring, single-use workspace invitations."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0034_workspace_invitations"
down_revision = "0033_platform_execution_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), sa.ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'member', 'viewer')", name="ck_workspace_invitations_allowed_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_workspace_invitations_token_hash"),
    )
    op.create_index("ix_workspace_invitations_workspace_id", "workspace_invitations", ["workspace_id"])
    op.create_index("ix_workspace_invitations_email", "workspace_invitations", ["email"])
    op.create_index("ix_workspace_invitations_workspace_created", "workspace_invitations", ["workspace_id", "created_at"])
    op.create_index("ix_workspace_invitations_workspace_email", "workspace_invitations", ["workspace_id", "email"])


def downgrade() -> None:
    op.drop_index("ix_workspace_invitations_workspace_email", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace_created", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_email", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace_id", table_name="workspace_invitations")
    op.drop_table("workspace_invitations")
