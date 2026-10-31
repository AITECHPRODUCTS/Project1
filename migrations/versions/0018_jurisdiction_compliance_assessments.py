"""Add evidence-backed jurisdiction compliance assessments."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0018_jurisdiction_compliance_assessments"
down_revision = "0017_signed_ad_performance_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jurisdiction_compliance_assessments",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("activity", sa.String(length=60), nullable=False),
        sa.Column("channels_json", sa.JSON(), nullable=False),
        sa.Column("jurisdictions_json", sa.JSON(), nullable=False),
        sa.Column("rule_evidence_json", sa.JSON(), nullable=False),
        sa.Column("coverage_summary_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_compliance_assessments_workspace_status", "jurisdiction_compliance_assessments", ["workspace_id", "status"])
    op.create_index("ix_compliance_assessments_workspace_activity", "jurisdiction_compliance_assessments", ["workspace_id", "activity"])
    op.create_index("ix_jurisdiction_compliance_assessments_workspace_id", "jurisdiction_compliance_assessments", ["workspace_id"])
    op.create_index("ix_jurisdiction_compliance_assessments_activity", "jurisdiction_compliance_assessments", ["activity"])
    op.create_index("ix_jurisdiction_compliance_assessments_status", "jurisdiction_compliance_assessments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_jurisdiction_compliance_assessments_activity", table_name="jurisdiction_compliance_assessments")
    op.drop_index("ix_jurisdiction_compliance_assessments_status", table_name="jurisdiction_compliance_assessments")
    op.drop_index("ix_jurisdiction_compliance_assessments_workspace_id", table_name="jurisdiction_compliance_assessments")
    op.drop_index("ix_compliance_assessments_workspace_activity", table_name="jurisdiction_compliance_assessments")
    op.drop_index("ix_compliance_assessments_workspace_status", table_name="jurisdiction_compliance_assessments")
    op.drop_table("jurisdiction_compliance_assessments")
