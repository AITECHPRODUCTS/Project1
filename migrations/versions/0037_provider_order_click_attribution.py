"""Add ClickBank TID to local-click attribution fields."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0037_provider_order_click_attribution"
down_revision = "0036_provider_order_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provider_order_observations", sa.Column("click_id", sa.String(length=80), nullable=True))
    op.add_column("provider_order_observations", sa.Column("attribution_status", sa.String(length=40), server_default="not_matched", nullable=False))
    with op.batch_alter_table("provider_order_observations") as batch_op:
        batch_op.create_check_constraint(
            "ck_provider_order_observations_attribution_status",
            "attribution_status IN ('not_matched', 'matched_clickbank_tid')",
        )
    op.create_index("ix_provider_order_observations_workspace_click", "provider_order_observations", ["workspace_id", "click_id"])


def downgrade() -> None:
    op.drop_index("ix_provider_order_observations_workspace_click", table_name="provider_order_observations")
    with op.batch_alter_table("provider_order_observations") as batch_op:
        batch_op.drop_constraint("ck_provider_order_observations_attribution_status", type_="check")
        batch_op.drop_column("attribution_status")
        batch_op.drop_column("click_id")
