"""Record human review of changed merchant terms source content."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0024_merchant_offer_evidence_review"
down_revision = "0023_merchant_offer_evidence_hash_comparison"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column(
            "review_status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'not_required'"),
        ),
    )
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column("review_decision", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
    )
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE merchant_offer_term_evidence_fetches "
        "SET review_status = 'pending_review' "
        "WHERE content_change_status = 'content_changed'"
    )


def downgrade() -> None:
    op.drop_column("merchant_offer_term_evidence_fetches", "reviewed_at")
    op.drop_column("merchant_offer_term_evidence_fetches", "reviewed_by")
    op.drop_column("merchant_offer_term_evidence_fetches", "review_notes")
    op.drop_column("merchant_offer_term_evidence_fetches", "review_decision")
    op.drop_column("merchant_offer_term_evidence_fetches", "review_status")
