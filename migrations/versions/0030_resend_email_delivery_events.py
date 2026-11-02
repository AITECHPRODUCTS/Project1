"""Persist verified Resend delivery outcomes and email-suppression state."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0030_resend_email_delivery_events"
down_revision = "0029_offer_qualification_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("email_suppressed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("email_suppression_reason", sa.String(length=80), nullable=True))
    op.create_table(
        "email_delivery_events",
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="resend"),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("scheduled_email_id", sa.String(length=36), nullable=True),
        sa.Column("consent_confirmation_id", sa.String(length=36), nullable=True),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("event_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_event_id", name="uq_email_delivery_events_provider_event_id"),
    )
    op.create_index("ix_email_delivery_events_workspace_id", "email_delivery_events", ["workspace_id"])
    op.create_index("ix_email_delivery_events_event_type", "email_delivery_events", ["event_type"])
    op.create_index(
        "ix_email_delivery_events_workspace_message",
        "email_delivery_events",
        ["workspace_id", "provider_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_delivery_events_workspace_message", table_name="email_delivery_events")
    op.drop_index("ix_email_delivery_events_event_type", table_name="email_delivery_events")
    op.drop_index("ix_email_delivery_events_workspace_id", table_name="email_delivery_events")
    op.drop_table("email_delivery_events")
    op.drop_column("leads", "email_suppression_reason")
    op.drop_column("leads", "email_suppressed_at")
