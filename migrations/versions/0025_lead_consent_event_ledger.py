"""Create an append-only, tenant-scoped lead consent evidence ledger."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0025_lead_consent_events"
down_revision = "0024_merchant_offer_evidence_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_consent_events",
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        # Deliberately no FK to leads: deleting a lead must not cascade away
        # immutable consent evidence. Governed unlink/retention remains required.
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=180), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_consent_events_workspace_id", "lead_consent_events", ["workspace_id"])
    op.create_index("ix_lead_consent_events_lead_id", "lead_consent_events", ["lead_id"])
    op.create_index("ix_lead_consent_events_event_type", "lead_consent_events", ["event_type"])
    op.create_index(
        "ix_lead_consent_workspace_lead_created",
        "lead_consent_events",
        ["workspace_id", "lead_id", "created_at"],
    )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION reject_lead_consent_event_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'lead consent events are append-only';
            END;
            $$ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER trg_lead_consent_event_append_only
            BEFORE UPDATE OR DELETE ON lead_consent_events
            FOR EACH ROW EXECUTE FUNCTION reject_lead_consent_event_mutation()
        """)
    elif dialect == "sqlite":
        op.execute("""
            CREATE TRIGGER trg_lead_consent_event_no_update
            BEFORE UPDATE ON lead_consent_events
            BEGIN
                SELECT RAISE(ABORT, 'lead consent events are append-only');
            END
        """)
        op.execute("""
            CREATE TRIGGER trg_lead_consent_event_no_delete
            BEFORE DELETE ON lead_consent_events
            BEGIN
                SELECT RAISE(ABORT, 'lead consent events are append-only');
            END
        """)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_lead_consent_event_append_only ON lead_consent_events")
        op.execute("DROP FUNCTION IF EXISTS reject_lead_consent_event_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_lead_consent_event_no_update")
        op.execute("DROP TRIGGER IF EXISTS trg_lead_consent_event_no_delete")

    op.drop_index("ix_lead_consent_workspace_lead_created", table_name="lead_consent_events")
    op.drop_index("ix_lead_consent_events_event_type", table_name="lead_consent_events")
    op.drop_index("ix_lead_consent_events_lead_id", table_name="lead_consent_events")
    op.drop_index("ix_lead_consent_events_workspace_id", table_name="lead_consent_events")
    op.drop_table("lead_consent_events")
