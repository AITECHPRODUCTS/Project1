"""Persist immutable human reviews for matched ClickBank order evidence."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0038_provider_order_reconciliation_reviews"
down_revision = "0037_provider_order_click_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_order_reconciliation_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("observation_id", sa.String(length=36), sa.ForeignKey("provider_order_observations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ledger_entry_id", sa.String(length=36), sa.ForeignKey("conversion_ledger_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewer_email", sa.String(length=320), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('matched_to_conversion', 'not_a_match', 'rejected_as_unreliable')",
            name="ck_provider_order_review_decision",
        ),
        sa.CheckConstraint(
            "(decision = 'matched_to_conversion' AND ledger_entry_id IS NOT NULL) OR "
            "(decision IN ('not_a_match', 'rejected_as_unreliable') AND ledger_entry_id IS NULL)",
            name="ck_provider_order_review_candidate",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "observation_id", name="uq_provider_order_review_workspace_observation"),
        sa.UniqueConstraint("workspace_id", "ledger_entry_id", name="uq_provider_order_review_workspace_ledger_entry"),
    )
    op.create_index("ix_provider_order_reconciliation_reviews_workspace_id", "provider_order_reconciliation_reviews", ["workspace_id"])
    op.create_index(
        "ix_provider_order_reviews_workspace_decision_time",
        "provider_order_reconciliation_reviews",
        ["workspace_id", "decision", "reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_order_reviews_workspace_decision_time", table_name="provider_order_reconciliation_reviews")
    op.drop_index("ix_provider_order_reconciliation_reviews_workspace_id", table_name="provider_order_reconciliation_reviews")
    op.drop_table("provider_order_reconciliation_reviews")
