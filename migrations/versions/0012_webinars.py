"""Persist workspace-scoped webinar events and consented registrations."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0012_webinars"
down_revision = "0011_durable_hitl_resume_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webinar_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("public_id", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(600), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("host_name", sa.String(200), nullable=False),
        sa.Column("host_bio", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(100), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("agenda_json", sa.JSON(), nullable=False),
        sa.Column("privacy_policy_url", sa.Text(), nullable=False),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("affiliate_disclosure", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_webinar_events_workspace_id_workspaces", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_webinar_events_public_id"),
    )
    op.create_index("ix_webinar_events_workspace_id", "webinar_events", ["workspace_id"])
    op.create_index("ix_webinar_events_status", "webinar_events", ["status"])
    op.create_index("ix_webinar_events_start_at", "webinar_events", ["start_at"])
    op.create_index("ix_webinar_events_workspace_status_start", "webinar_events", ["workspace_id", "status", "start_at"])
    op.create_table(
        "webinar_registrations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("webinar_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_text_snapshot", sa.Text(), nullable=False),
        sa.Column("consent_source", sa.String(100), nullable=False),
        sa.Column("marketing_consent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_webinar_registrations_workspace_id_workspaces", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["webinar_id"], ["webinar_events.id"], name="fk_webinar_registrations_webinar_events", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "webinar_id", "email", name="uq_webinar_registrations_workspace_event_email"),
    )
    op.create_index("ix_webinar_registrations_workspace_id", "webinar_registrations", ["workspace_id"])
    op.create_index("ix_webinar_registrations_webinar_id", "webinar_registrations", ["webinar_id"])
    op.create_index("ix_webinar_registrations_workspace_webinar_created", "webinar_registrations", ["workspace_id", "webinar_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_webinar_registrations_workspace_webinar_created", table_name="webinar_registrations")
    op.drop_index("ix_webinar_registrations_webinar_id", table_name="webinar_registrations")
    op.drop_index("ix_webinar_registrations_workspace_id", table_name="webinar_registrations")
    op.drop_table("webinar_registrations")
    op.drop_index("ix_webinar_events_workspace_status_start", table_name="webinar_events")
    op.drop_index("ix_webinar_events_start_at", table_name="webinar_events")
    op.drop_index("ix_webinar_events_status", table_name="webinar_events")
    op.drop_index("ix_webinar_events_workspace_id", table_name="webinar_events")
    op.drop_table("webinar_events")
