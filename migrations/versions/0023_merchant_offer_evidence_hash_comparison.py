"""Persist comparisons between successive public terms page retrievals."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0023_merchant_offer_evidence_hash_comparison"
down_revision = "0022_merchant_offer_evidence_fetches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column("previous_content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "merchant_offer_term_evidence_fetches",
        sa.Column(
            "content_change_status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'not_comparable'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("merchant_offer_term_evidence_fetches", "content_change_status")
    op.drop_column("merchant_offer_term_evidence_fetches", "previous_content_sha256")
