"""Add configurable double opt-in confirmation state and expiring token records."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0026_email_double_opt_in"
down_revision = "0025_lead_consent_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("email_consent_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "email_consent_confirmations",
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_consent_confirmations_workspace_id", "email_consent_confirmations", ["workspace_id"])
    op.create_index("ix_email_consent_confirmations_lead_id", "email_consent_confirmations", ["lead_id"])
    op.create_index("ix_email_consent_confirmations_status", "email_consent_confirmations", ["status"])
    op.create_index("ix_email_consent_confirmations_token_hash", "email_consent_confirmations", ["token_hash"], unique=True)
    op.create_index("ix_email_consent_workspace_lead_created", "email_consent_confirmations", ["workspace_id", "lead_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_consent_workspace_lead_created", table_name="email_consent_confirmations")
    op.drop_index("ix_email_consent_confirmations_token_hash", table_name="email_consent_confirmations")
    op.drop_index("ix_email_consent_confirmations_status", table_name="email_consent_confirmations")
    op.drop_index("ix_email_consent_confirmations_lead_id", table_name="email_consent_confirmations")
    op.drop_index("ix_email_consent_confirmations_workspace_id", table_name="email_consent_confirmations")
    op.drop_table("email_consent_confirmations")
    op.drop_column("leads", "email_consent_confirmed_at")
