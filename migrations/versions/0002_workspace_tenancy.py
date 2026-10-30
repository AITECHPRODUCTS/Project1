"""Add workspace membership and scope tenant-owned operational records.

Legacy rows are assigned to an inaccessible quarantine workspace rather than
silently exposing them to the first user who signs in. New authenticated writes
must supply a verified active workspace context.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_workspace_tenancy"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

LEGACY_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
TENANT_TABLES = (
    "campaigns",
    "click_events",
    "conversions",
    "workflow_runs",
    "paused_sessions",
    "audit_logs",
    "content_assets",
    "leads",
    "scheduled_emails",
    "mail_commissions",
    "payout_thresholds",
    "resource_usage",
)


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_workspace_user"),
    )
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    op.execute(
        sa.text(
            "INSERT INTO workspaces (id, name, slug, owner_user_id) "
            "VALUES (:id, :name, :slug, NULL)"
        ).bindparams(
            id=LEGACY_WORKSPACE_ID,
            name="Quarantined migrated records",
            slug="legacy-quarantine",
        )
    )

    for table in TENANT_TABLES:
        # SQLite cannot ALTER a table to add a foreign-key constraint. Batch mode
        # uses Alembic's copy-and-move strategy on SQLite and native ALTER on
        # PostgreSQL, keeping the same constraint on both supported databases.
        with op.batch_alter_table(table, recreate="auto") as batch_op:
            batch_op.add_column(
                sa.Column("workspace_id", sa.String(length=36), nullable=True)
            )
            batch_op.create_foreign_key(
                f"fk_{table}_workspace_id_workspaces",
                "workspaces",
                ["workspace_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])
        op.execute(
            sa.text(f'UPDATE "{table}" SET workspace_id = :legacy_id WHERE workspace_id IS NULL')
            .bindparams(legacy_id=LEGACY_WORKSPACE_ID)
        )

    # Historical global uniqueness is replaced by workspace-local uniqueness.
    op.drop_index("ix_leads_email", table_name="leads")
    op.create_index("ix_leads_email", "leads", ["email"], unique=False)
    op.create_index("uq_leads_workspace_email", "leads", ["workspace_id", "email"], unique=True)

    op.drop_index("ix_mail_commissions_message_id", table_name="mail_commissions")
    op.create_index("ix_mail_commissions_message_id", "mail_commissions", ["message_id"], unique=False)
    op.create_index(
        "uq_mail_commissions_workspace_message",
        "mail_commissions",
        ["workspace_id", "message_id"],
        unique=True,
    )

    op.create_table(
        "performance_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("memory_key", sa.String(length=64), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("conversion_count", sa.Integer(), nullable=False),
        sa.Column("click_count", sa.Integer(), nullable=False),
        sa.Column("conversion_rate", sa.Float(), nullable=False),
        sa.Column("commission_recorded", sa.Float(), nullable=False),
        sa.Column("source_networks", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_memories_memory_key", "performance_memories", ["memory_key"])
    op.create_index("ix_performance_memories_status", "performance_memories", ["status"])
    op.create_index("ix_performance_memories_workspace_id", "performance_memories", ["workspace_id"])
    op.create_index(
        "uq_performance_memory_workspace_key",
        "performance_memories",
        ["workspace_id", "memory_key"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    duplicate_lead = bind.execute(
        sa.text("SELECT email FROM leads GROUP BY email HAVING COUNT(*) > 1 LIMIT 1")
    ).first()
    duplicate_mail = bind.execute(
        sa.text("SELECT message_id FROM mail_commissions GROUP BY message_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first()
    if duplicate_lead or duplicate_mail:
        raise RuntimeError(
            "Cannot downgrade workspace tenancy safely while duplicate emails or mail message IDs "
            "exist in different workspaces. Export/reconcile the duplicates before retrying."
        )

    op.drop_index("uq_performance_memory_workspace_key", table_name="performance_memories")
    op.drop_index("ix_performance_memories_workspace_id", table_name="performance_memories")
    op.drop_index("ix_performance_memories_status", table_name="performance_memories")
    op.drop_index("ix_performance_memories_memory_key", table_name="performance_memories")
    op.drop_table("performance_memories")

    op.drop_index("uq_leads_workspace_email", table_name="leads")
    op.drop_index("ix_leads_email", table_name="leads")
    op.create_index("ix_leads_email", "leads", ["email"], unique=True)
    op.drop_index("uq_mail_commissions_workspace_message", table_name="mail_commissions")
    op.drop_index("ix_mail_commissions_message_id", table_name="mail_commissions")
    op.create_index("ix_mail_commissions_message_id", "mail_commissions", ["message_id"], unique=True)

    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        with op.batch_alter_table(table, recreate="auto") as batch_op:
            batch_op.drop_constraint(
                f"fk_{table}_workspace_id_workspaces",
                type_="foreignkey",
            )
            batch_op.drop_column("workspace_id")

    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_workspace_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
