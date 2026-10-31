"""Add platform incident records and idempotent operator retry claims."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0041_platform_operations"
down_revision = "0040_account_personas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_incidents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source_resource_id", sa.String(length=255), nullable=True),
        sa.Column("source_workspace_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=320), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=320), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_platform_incidents_severity"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved')", name="ck_platform_incidents_status"),
        sa.ForeignKeyConstraint(["source_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_resource_id", name="uq_platform_incidents_source"),
    )
    op.create_index("ix_platform_incidents_status_created", "platform_incidents", ["status", "created_at"], unique=False)
    op.create_index("ix_platform_incidents_severity_status", "platform_incidents", ["severity", "status"], unique=False)
    op.create_index(
        "uq_audit_workflow_operator_retry_claim",
        "audit_logs",
        ["resource_id"],
        unique=True,
        sqlite_where=sa.text("action = 'workflow.operator_retry_claimed' AND resource_id IS NOT NULL"),
        postgresql_where=sa.text("action = 'workflow.operator_retry_claimed' AND resource_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_audit_workflow_operator_retry_claim", table_name="audit_logs")
    op.drop_index("ix_platform_incidents_severity_status", table_name="platform_incidents")
    op.drop_index("ix_platform_incidents_status_created", table_name="platform_incidents")
    op.drop_table("platform_incidents")
