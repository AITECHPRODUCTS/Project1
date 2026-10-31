"""Add immutable Affiliate/Publisher and Merchant/Product Owner account personas."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0040_account_personas"
down_revision = "0039_offer_evidence_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_accounts", sa.Column("account_type", sa.String(length=40), nullable=True))
    op.execute("UPDATE user_accounts SET account_type = 'platform_admin' WHERE is_admin = TRUE")
    op.execute(
        """
        UPDATE user_accounts
        SET account_type = 'merchant_product_owner'
        WHERE is_admin = FALSE
          AND id IN (
              SELECT workspaces.owner_user_id
              FROM workspaces
              INNER JOIN merchant_offers ON merchant_offers.workspace_id = workspaces.id
              WHERE workspaces.owner_user_id IS NOT NULL
          )
        """
    )
    op.execute("UPDATE user_accounts SET account_type = 'affiliate_publisher' WHERE account_type IS NULL")
    with op.batch_alter_table("user_accounts") as batch:
        batch.alter_column(
            "account_type", existing_type=sa.String(length=40),
            nullable=False, server_default=sa.text("'affiliate_publisher'"),
        )
        batch.create_check_constraint(
            "ck_user_accounts_account_type",
            "account_type IN ('affiliate_publisher', 'merchant_product_owner', 'platform_admin')",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_accounts") as batch:
        batch.drop_constraint("ck_user_accounts_account_type", type_="check")
        batch.drop_column("account_type")
