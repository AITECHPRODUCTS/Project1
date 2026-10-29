"""Add workspace-owned saved offer shortlists."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0028_offer_shortlists"
down_revision = "0027_skill_runtime_handlers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offer_shortlists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "name", name="uq_offer_shortlist_workspace_name"),
    )
    op.create_index("ix_offer_shortlists_workspace_id", "offer_shortlists", ["workspace_id"])
    op.create_table(
        "offer_shortlist_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("shortlist_id", sa.String(length=36), sa.ForeignKey("offer_shortlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_id", sa.String(length=36), sa.ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("shortlist_id", "offer_id", name="uq_offer_shortlist_item_offer"),
    )
    op.create_index("ix_offer_shortlist_items_workspace_id", "offer_shortlist_items", ["workspace_id"])
    op.create_index("ix_offer_shortlist_items_shortlist_id", "offer_shortlist_items", ["shortlist_id"])
    op.create_index("ix_offer_shortlist_items_offer_id", "offer_shortlist_items", ["offer_id"])


def downgrade() -> None:
    op.drop_index("ix_offer_shortlist_items_offer_id", table_name="offer_shortlist_items")
    op.drop_index("ix_offer_shortlist_items_shortlist_id", table_name="offer_shortlist_items")
    op.drop_index("ix_offer_shortlist_items_workspace_id", table_name="offer_shortlist_items")
    op.drop_table("offer_shortlist_items")
    op.drop_index("ix_offer_shortlists_workspace_id", table_name="offer_shortlists")
    op.drop_table("offer_shortlists")
