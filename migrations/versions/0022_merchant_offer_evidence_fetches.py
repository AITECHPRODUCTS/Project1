"""Store immutable results from explicit merchant-terms evidence retrievals."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0022_merchant_offer_evidence_fetches"
down_revision = "0021_merchant_offer_term_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_offer_term_evidence_fetches",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("merchant_offer_id", sa.String(length=36), nullable=False),
        sa.Column("term_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetch_status", sa.String(length=40), nullable=False),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("response_bytes", sa.Integer(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("text_excerpt", sa.Text(), nullable=False),
        sa.Column("etag", sa.String(length=500), nullable=True),
        sa.Column("last_modified", sa.String(length=200), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provider_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_by", sa.String(length=320), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_offer_id"], ["merchant_offers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["term_snapshot_id"], ["merchant_offer_term_snapshots.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_merchant_offer_evidence_fetch_scope_time",
        "merchant_offer_term_evidence_fetches",
        ["workspace_id", "merchant_offer_id", "term_snapshot_id", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_merchant_offer_evidence_fetch_scope_time",
        table_name="merchant_offer_term_evidence_fetches",
    )
    op.drop_table("merchant_offer_term_evidence_fetches")
