"""Allow multiple independently attributed publisher links per approved program."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0043_multiple_affiliate_program_links"
down_revision = "0042_merchant_partner_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("affiliate_program_links") as batch:
        batch.drop_constraint("uq_affiliate_program_link_application", type_="unique")
        batch.add_column(sa.Column("link_label", sa.String(length=120), nullable=False, server_default="Primary link"))
        batch.add_column(sa.Column("destination_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.create_unique_constraint(
            "uq_affiliate_program_link_label",
            ["workspace_id", "application_id", "link_label"],
        )

    op.execute(
        sa.text(
            "UPDATE affiliate_program_links "
            "SET destination_url = (SELECT primary_destination FROM campaigns "
            "WHERE campaigns.id = affiliate_program_links.campaign_id) "
            "WHERE destination_url IS NULL"
        )
    )

    with op.batch_alter_table("affiliate_program_links") as batch:
        batch.alter_column("destination_url", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    connection = op.get_bind()
    duplicate_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT application_id FROM affiliate_program_links "
            "GROUP BY application_id HAVING COUNT(*) > 1"
            ")"
        )
    ).scalar_one()
    if duplicate_count:
        raise RuntimeError(
            "Cannot downgrade multiple affiliate links while applications have more than one link."
        )

    with op.batch_alter_table("affiliate_program_links") as batch:
        batch.drop_constraint("uq_affiliate_program_link_label", type_="unique")
        batch.drop_column("is_primary")
        batch.drop_column("destination_url")
        batch.drop_column("link_label")
        batch.create_unique_constraint(
            "uq_affiliate_program_link_application",
            ["workspace_id", "application_id"],
        )
