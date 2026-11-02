"""Persist encrypted, workspace-scoped provider account connections."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0035_provider_account_connections"
down_revision = "0034_workspace_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_account_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("credential_ciphertext", sa.Text(), nullable=True),
        sa.Column("credential_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("credential_key_version", sa.Integer(), nullable=False),
        sa.Column("account_nicknames_json", sa.JSON(), nullable=False),
        sa.Column("capabilities_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
        sa.CheckConstraint("status IN ('connected_read_only', 'degraded', 'disconnected')", name="ck_provider_connections_status"),
        sa.CheckConstraint(
            "(status = 'disconnected' AND credential_ciphertext IS NULL AND credential_fingerprint IS NULL) OR "
            "(status IN ('connected_read_only', 'degraded') AND credential_ciphertext IS NOT NULL AND credential_fingerprint IS NOT NULL)",
            name="ck_provider_connections_credential_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "provider_id", "credential_fingerprint", name="uq_provider_connections_workspace_provider_fingerprint"),
    )
    op.create_index("ix_provider_account_connections_workspace_id", "provider_account_connections", ["workspace_id"])
    op.create_index("ix_provider_account_connections_provider_id", "provider_account_connections", ["provider_id"])
    op.create_index("ix_provider_account_connections_status", "provider_account_connections", ["status"])
    op.create_index("ix_provider_connections_workspace_provider_status", "provider_account_connections", ["workspace_id", "provider_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_provider_connections_workspace_provider_status", table_name="provider_account_connections")
    op.drop_index("ix_provider_account_connections_status", table_name="provider_account_connections")
    op.drop_index("ix_provider_account_connections_provider_id", table_name="provider_account_connections")
    op.drop_index("ix_provider_account_connections_workspace_id", table_name="provider_account_connections")
    op.drop_table("provider_account_connections")
