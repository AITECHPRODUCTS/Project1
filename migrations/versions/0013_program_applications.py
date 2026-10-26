"""Persist workspace-scoped affiliate program application packets."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0013_program_applications"
down_revision = "0012_webinars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affiliate_program_applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=160), nullable=False),
        sa.Column("program_name", sa.String(length=240), nullable=False),
        sa.Column("program_url", sa.Text(), nullable=False),
        sa.Column("publisher_website_url", sa.Text(), nullable=False),
        sa.Column("audience_description", sa.Text(), nullable=False),
        sa.Column("monthly_visitors", sa.Integer(), nullable=True),
        sa.Column("traffic_sources_json", sa.JSON(), nullable=False),
        sa.Column("promotion_channels_json", sa.JSON(), nullable=False),
        sa.Column("primary_regions_json", sa.JSON(), nullable=False),
        sa.Column("promotion_plan", sa.Text(), nullable=False),
        sa.Column("evidence_urls_json", sa.JSON(), nullable=False),
        sa.Column("compliance_answers_json", sa.JSON(), nullable=False),
        sa.Column("readiness_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_submission_status", sa.String(length=40), nullable=False),
        sa.Column("provider_application_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_program_applications_workspace_id_workspaces", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_affiliate_program_applications_provider", "affiliate_program_applications", ["provider"])
    op.create_index("ix_affiliate_program_applications_status", "affiliate_program_applications", ["status"])
    op.create_index("ix_affiliate_program_applications_created_at", "affiliate_program_applications", ["created_at"])
    op.create_index("ix_program_applications_workspace_status_created", "affiliate_program_applications", ["workspace_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_program_applications_workspace_status_created", table_name="affiliate_program_applications")
    op.drop_index("ix_affiliate_program_applications_created_at", table_name="affiliate_program_applications")
    op.drop_index("ix_affiliate_program_applications_status", table_name="affiliate_program_applications")
    op.drop_index("ix_affiliate_program_applications_provider", table_name="affiliate_program_applications")
    op.drop_table("affiliate_program_applications")
