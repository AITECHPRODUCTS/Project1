"""Scope provider conversion idempotency keys to each workspace.

Previously, a global unique key prevented two tenants from independently
recording the same provider event identifier and could leak duplicate outcomes
across workspace boundaries.
"""
from __future__ import annotations

from alembic import op

revision = "0005_workspace_scoped_conversion_identity"
down_revision = "0004_ad_performance_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic creates version_num as VARCHAR(32). This project’s stable revision
    # identifiers exceed that limit, which PostgreSQL enforces (unlike SQLite).
    # Widen the bookkeeping column before Alembic stamps this revision.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(255)"
        )
    with op.batch_alter_table("conversions", recreate="auto") as batch_op:
        batch_op.drop_constraint("uq_conversion_network_external_event", type_="unique")
        batch_op.create_index(
            "uq_conversion_workspace_network_external_event",
            ["workspace_id", "network", "external_event_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("conversions", recreate="auto") as batch_op:
        batch_op.drop_index("uq_conversion_workspace_network_external_event")
        batch_op.create_unique_constraint(
            "uq_conversion_network_external_event",
            ["network", "external_event_id"],
        )
