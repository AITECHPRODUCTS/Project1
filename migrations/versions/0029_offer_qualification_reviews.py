"""Add workspace-scoped offer qualification reviews."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0029_offer_qualification_reviews"
down_revision = "0028_offer_shortlists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offer_qualification_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("offer_id", sa.String(length=36), sa.ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("account_eligibility", sa.String(length=20), nullable=False),
        sa.Column("geography_fit", sa.String(length=20), nullable=False),
        sa.Column("traffic_source_fit", sa.String(length=20), nullable=False),
        sa.Column("terms_review", sa.String(length=20), nullable=False),
        sa.Column("landing_page_review", sa.String(length=20), nullable=False),
        sa.Column("disclosure_review", sa.String(length=20), nullable=False),
        sa.Column("evidence_urls", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("reviewed_by", sa.String(length=320), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "offer_id", name="uq_offer_qualification_workspace_offer"),
    )
    op.create_index("ix_offer_qualification_reviews_workspace_id", "offer_qualification_reviews", ["workspace_id"])
    op.create_index("ix_offer_qualification_reviews_offer_id", "offer_qualification_reviews", ["offer_id"])


def downgrade() -> None:
    op.drop_index("ix_offer_qualification_reviews_offer_id", table_name="offer_qualification_reviews")
    op.drop_index("ix_offer_qualification_reviews_workspace_id", table_name="offer_qualification_reviews")
    op.drop_table("offer_qualification_reviews")
