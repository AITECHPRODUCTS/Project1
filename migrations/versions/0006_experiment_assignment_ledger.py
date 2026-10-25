"""Persist workspace-scoped A/B assignments and idempotent experiment events."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_experiment_assignment_ledger"
down_revision = "0005_workspace_scoped_conversion_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("experiment_key", sa.String(length=180), nullable=False),
        sa.Column("visitor_id", sa.String(length=255), nullable=False),
        sa.Column("variant", sa.String(length=1), nullable=False),
        sa.Column("headline_a", sa.Text(), nullable=False),
        sa.Column("headline_b", sa.Text(), nullable=False),
        sa.Column("assigned_headline", sa.Text(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_experiment_assignments_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_experiment_assignment_workspace_key_visitor",
        "experiment_assignments",
        ["workspace_id", "experiment_key", "visitor_id"],
        unique=True,
    )
    op.create_index(
        "ix_experiment_assignment_workspace_key_variant",
        "experiment_assignments",
        ["workspace_id", "experiment_key", "variant"],
    )

    op.create_table(
        "experiment_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_experiment_events_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["experiment_assignments.id"],
            name="fk_experiment_events_assignment_id_experiment_assignments",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_experiment_event_workspace_event_id",
        "experiment_events",
        ["workspace_id", "event_id"],
        unique=True,
    )
    op.create_index(
        "ix_experiment_event_workspace_assignment_type",
        "experiment_events",
        ["workspace_id", "assignment_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_event_workspace_assignment_type", table_name="experiment_events")
    op.drop_index("uq_experiment_event_workspace_event_id", table_name="experiment_events")
    op.drop_table("experiment_events")
    op.drop_index("ix_experiment_assignment_workspace_key_variant", table_name="experiment_assignments")
    op.drop_index("uq_experiment_assignment_workspace_key_visitor", table_name="experiment_assignments")
    op.drop_table("experiment_assignments")
