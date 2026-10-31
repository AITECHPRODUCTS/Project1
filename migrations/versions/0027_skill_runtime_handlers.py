"""Add a code-owned runtime handler binding to governed skill packages."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0027_skill_runtime_handlers"
down_revision = "0026_email_double_opt_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill_packages",
        sa.Column("runtime_handler", sa.String(length=80), server_default="none", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("skill_packages", "runtime_handler")
