"""Add persistent merchant-publisher conversations and align the tracked-link Boolean default."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0044_partner_messaging"
down_revision = "0043_multiple_affiliate_program_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("affiliate_program_links") as batch:
        batch.alter_column(
            "is_primary",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.text("true"),
        )

    op.create_table(
        "partner_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_workspace_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_partner_conversations_status"),
        sa.CheckConstraint("workspace_id <> merchant_workspace_id", name="ck_partner_conversations_distinct_parties"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merchant_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["marketplace_applications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_partner_conversation_application"),
    )
    op.create_index("ix_partner_conversations_workspace_id", "partner_conversations", ["workspace_id"])
    op.create_index("ix_partner_conversations_merchant_workspace_id", "partner_conversations", ["merchant_workspace_id"])
    op.create_index("ix_partner_conversations_application_id", "partner_conversations", ["application_id"])
    op.create_index("ix_partner_conversations_publisher_last_message", "partner_conversations", ["workspace_id", "last_message_at"])
    op.create_index("ix_partner_conversations_merchant_last_message", "partner_conversations", ["merchant_workspace_id", "last_message_at"])

    op.create_table(
        "partner_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sender_workspace_id", sa.String(length=36), nullable=False),
        sa.Column("sender_user_id", sa.String(length=36), nullable=True),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_by_workspace_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(body)) > 0 AND length(body) <= 5000", name="ck_partner_messages_body_length"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["conversation_id"], ["partner_conversations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sender_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["read_by_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_partner_messages_workspace_id", "partner_messages", ["workspace_id"])
    op.create_index("ix_partner_messages_conversation_id", "partner_messages", ["conversation_id"])
    op.create_index("ix_partner_messages_sender_workspace_id", "partner_messages", ["sender_workspace_id"])
    op.create_index("ix_partner_messages_conversation_created", "partner_messages", ["conversation_id", "created_at"])
    op.create_index("ix_partner_messages_workspace_created", "partner_messages", ["workspace_id", "created_at"])
    op.create_index("ix_partner_messages_conversation_unread", "partner_messages", ["conversation_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_partner_messages_conversation_unread", table_name="partner_messages")
    op.drop_index("ix_partner_messages_workspace_created", table_name="partner_messages")
    op.drop_index("ix_partner_messages_conversation_created", table_name="partner_messages")
    op.drop_index("ix_partner_messages_sender_workspace_id", table_name="partner_messages")
    op.drop_index("ix_partner_messages_conversation_id", table_name="partner_messages")
    op.drop_index("ix_partner_messages_workspace_id", table_name="partner_messages")
    op.drop_table("partner_messages")

    op.drop_index("ix_partner_conversations_merchant_last_message", table_name="partner_conversations")
    op.drop_index("ix_partner_conversations_publisher_last_message", table_name="partner_conversations")
    op.drop_index("ix_partner_conversations_application_id", table_name="partner_conversations")
    op.drop_index("ix_partner_conversations_merchant_workspace_id", table_name="partner_conversations")
    op.drop_index("ix_partner_conversations_workspace_id", table_name="partner_conversations")
    op.drop_table("partner_conversations")
