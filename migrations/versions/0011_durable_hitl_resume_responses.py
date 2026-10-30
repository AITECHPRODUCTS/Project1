"""Persist encrypted human-in-the-loop responses for workflow recovery."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_durable_hitl_resume_responses"
down_revision = "0010_durable_workflow_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paused_sessions",
        sa.Column("verification_response_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("paused_sessions", "verification_response_encrypted")
