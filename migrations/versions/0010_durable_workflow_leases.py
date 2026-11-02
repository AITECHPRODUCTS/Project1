"""Persist leases, heartbeats and attempt counters for workflow recovery."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_durable_workflow_leases"
down_revision = "0009_external_action_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_runs", sa.Column("lease_owner", sa.String(length=100), nullable=True))
    op.add_column("workflow_runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "workflow_runs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_workflow_runs_status_lease_expiry",
        "workflow_runs",
        ["status", "lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_runs_workspace_status_lease_expiry",
        "workflow_runs",
        ["workspace_id", "status", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_workspace_status_lease_expiry", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_status_lease_expiry", table_name="workflow_runs")
    op.drop_column("workflow_runs", "attempt_count")
    op.drop_column("workflow_runs", "heartbeat_at")
    op.drop_column("workflow_runs", "lease_expires_at")
    op.drop_column("workflow_runs", "lease_owner")
