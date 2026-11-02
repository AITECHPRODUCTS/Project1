"""Create the append-only decimal conversion and commission ledger."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_conversion_ledger"
down_revision = "0006_experiment_assignment_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversion_ledger_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("network", sa.String(length=100), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("click_id", sa.String(length=80), nullable=True),
        sa.Column("entry_type", sa.String(length=40), nullable=False),
        sa.Column("original_event_id", sa.String(length=255), nullable=True),
        sa.Column("commission_amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("revenue_amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("evidence_status", sa.String(length=40), nullable=False),
        sa.Column("source_event_json", sa.JSON(), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_conv_ledger_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "network", "external_event_id",
            name="uq_conv_ledger_ws_network_event",
        ),
    )
    op.create_index("ix_conversion_ledger_entries_workspace_id", "conversion_ledger_entries", ["workspace_id"])
    op.create_index("ix_conversion_ledger_entries_network", "conversion_ledger_entries", ["network"])
    op.create_index("ix_conversion_ledger_entries_click_id", "conversion_ledger_entries", ["click_id"])
    op.create_index("ix_conversion_ledger_entries_currency", "conversion_ledger_entries", ["currency"])
    op.create_index("ix_conversion_ledger_entries_status", "conversion_ledger_entries", ["status"])
    op.create_index("ix_conversion_ledger_entries_evidence_status", "conversion_ledger_entries", ["evidence_status"])
    op.create_index("ix_conversion_ledger_entries_created_at", "conversion_ledger_entries", ["created_at"])
    op.create_index("ix_conv_ledger_ws_created", "conversion_ledger_entries", ["workspace_id", "created_at"])

    # Preserve all existing conversion rows as explicitly unverified opening observations.
    op.execute(sa.text("""
        INSERT INTO conversion_ledger_entries (
            id, workspace_id, network, external_event_id, click_id, entry_type,
            original_event_id, commission_amount, revenue_amount, currency,
            status, evidence_status, source_event_json, observed_at, created_at
        )
        SELECT
            id, workspace_id, network, external_event_id, click_id, 'historical_snapshot',
            NULL, CAST(commission AS NUMERIC(18, 6)), CAST(revenue AS NUMERIC(18, 6)),
            COALESCE(NULLIF(UPPER(TRIM(currency)), ''), 'USD'),
            COALESCE(status, 'pending'), 'legacy_unverified',
            COALESCE(event_json, '{}'),
            COALESCE(occurred_at, created_at, CURRENT_TIMESTAMP),
            COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM conversions
    """))

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION reject_conversion_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'conversion ledger is append-only';
            END;
            $$ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER trg_conv_ledger_append_only
            BEFORE UPDATE OR DELETE ON conversion_ledger_entries
            FOR EACH ROW EXECUTE FUNCTION reject_conversion_ledger_mutation()
        """)
    elif dialect == "sqlite":
        op.execute("""
            CREATE TRIGGER trg_conv_ledger_no_update
            BEFORE UPDATE ON conversion_ledger_entries
            BEGIN
                SELECT RAISE(ABORT, 'conversion ledger is append-only');
            END
        """)
        op.execute("""
            CREATE TRIGGER trg_conv_ledger_no_delete
            BEFORE DELETE ON conversion_ledger_entries
            BEGIN
                SELECT RAISE(ABORT, 'conversion ledger is append-only');
            END
        """)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_conv_ledger_append_only ON conversion_ledger_entries")
        op.execute("DROP FUNCTION IF EXISTS reject_conversion_ledger_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_conv_ledger_no_update")
        op.execute("DROP TRIGGER IF EXISTS trg_conv_ledger_no_delete")

    op.drop_index("ix_conv_ledger_ws_created", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_created_at", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_evidence_status", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_status", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_currency", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_click_id", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_network", table_name="conversion_ledger_entries")
    op.drop_index("ix_conversion_ledger_entries_workspace_id", table_name="conversion_ledger_entries")
    op.drop_table("conversion_ledger_entries")
