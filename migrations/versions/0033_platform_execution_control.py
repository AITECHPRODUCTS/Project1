"""Add a durable Platform Super Admin provider-write pause switch."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0033_platform_execution_control"
down_revision = "0032_workspace_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_execution_controls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outbound_actions_paused", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(length=320), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_platform_execution_controls_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text(
        "INSERT INTO platform_execution_controls (id, outbound_actions_paused) VALUES (1, false)"
    ))


def downgrade() -> None:
    op.drop_table("platform_execution_controls")
