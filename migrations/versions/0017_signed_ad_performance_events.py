"""Add idempotency and signature provenance to signed ad observations."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0017_signed_ad_performance_events"
down_revision = "0016_ad_budget_guardrails"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("ad_performance_observations") as batch_op:
        batch_op.add_column(sa.Column("provider_event_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_signature_sha256", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_ad_perf_observation_workspace_platform_event",
            ["workspace_id", "platform", "provider_event_id"],
        )

def downgrade() -> None:
    with op.batch_alter_table("ad_performance_observations") as batch_op:
        batch_op.drop_constraint("uq_ad_perf_observation_workspace_platform_event", type_="unique")
        batch_op.drop_column("source_signature_sha256")
        batch_op.drop_column("provider_event_id")
