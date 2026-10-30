"""Persist idempotency claims and outcomes for external provider writes."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_external_action_idempotency"
down_revision = "0008_scheduled_email_delivery_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("remote_id", sa.String(length=255), nullable=True),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "action_type", "idempotency_key",
            name="uq_external_action_ws_type_key",
        ),
    )
    op.create_index("ix_external_actions_workspace_id", "external_actions", ["workspace_id"])
    op.create_index("ix_external_actions_status", "external_actions", ["status"])
    op.create_index(
        "ix_external_actions_workspace_status_created",
        "external_actions",
        ["workspace_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_actions_workspace_status_created", table_name="external_actions")
    op.drop_index("ix_external_actions_status", table_name="external_actions")
    op.drop_index("ix_external_actions_workspace_id", table_name="external_actions")
    op.drop_table("external_actions")
