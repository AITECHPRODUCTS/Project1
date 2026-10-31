"""Add lease timestamps for atomic scheduled-email delivery claims."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_scheduled_email_delivery_claims"
down_revision = "0007_conversion_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scheduled_emails",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_scheduled_email_workspace_claim",
        "scheduled_emails",
        ["workspace_id", "status", "claimed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_email_workspace_claim", table_name="scheduled_emails")
    op.drop_column("scheduled_emails", "claimed_at")
