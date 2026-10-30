"""Merge provider catalog and order reconciliation migration heads."""
from __future__ import annotations

from alembic import op  # noqa: F401

revision = "0039_merge_provider_catalog_and_reconciliation"
down_revision = (
    "0038_provider_catalog_observations",
    "0038_provider_order_reconciliation_reviews",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both 0038 revisions are additive siblings rooted at 0037. This merge
    # revision joins their graph without changing either schema.
    pass


def downgrade() -> None:
    # Alembic downgrades the merged parents explicitly; the merge itself has
    # no schema operations to reverse.
    pass
