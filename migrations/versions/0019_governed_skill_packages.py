"""Persist versioned workspace skill packages and review results."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_governed_skill_packages"
down_revision = "0018_jurisdiction_compliance_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_packages",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("skill_id", sa.String(length=140), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("stage", sa.String(length=2), nullable=False),
        sa.Column("capabilities_json", sa.JSON(), nullable=False),
        sa.Column("input_schema_json", sa.JSON(), nullable=False),
        sa.Column("output_schema_json", sa.JSON(), nullable=False),
        sa.Column("instructions_markdown", sa.Text(), nullable=False),
        sa.Column("fixtures_json", sa.JSON(), nullable=False),
        sa.Column("validation_report_json", sa.JSON(), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "workspace_id", "skill_id", "version",
            name="uq_skill_packages_workspace_skill_version",
        ),
    )
    op.create_index("ix_skill_packages_workspace_id", "skill_packages", ["workspace_id"])
    op.create_index("ix_skill_packages_skill_id", "skill_packages", ["skill_id"])
    op.create_index("ix_skill_packages_stage", "skill_packages", ["stage"])
    op.create_index("ix_skill_packages_status", "skill_packages", ["status"])
    op.create_index(
        "ix_skill_packages_workspace_status_created",
        "skill_packages",
        ["workspace_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_skill_packages_workspace_status_created", table_name="skill_packages")
    op.drop_index("ix_skill_packages_status", table_name="skill_packages")
    op.drop_index("ix_skill_packages_stage", table_name="skill_packages")
    op.drop_index("ix_skill_packages_skill_id", table_name="skill_packages")
    op.drop_index("ix_skill_packages_workspace_id", table_name="skill_packages")
    op.drop_table("skill_packages")
