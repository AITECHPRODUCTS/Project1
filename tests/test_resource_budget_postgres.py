from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from backend.database import SessionLocal, engine
from backend.services.resource_budget import _acquire_workspace_budget_lock


@pytest.mark.asyncio
async def test_postgres_budget_lock_blocks_second_connection_until_commit():
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL integration CI job")

    workspace_id = f"budget-lock-{uuid.uuid4().hex}"
    namespace = "omni-affiliate-os/resource-budget/v1"
    probe = select(
        func.pg_try_advisory_xact_lock(
            func.hashtext(namespace),
            func.hashtext(workspace_id),
        )
    )

    async with SessionLocal() as first:
        async with SessionLocal() as second:
            await _acquire_workspace_budget_lock(first, workspace_id)
            assert await second.scalar(probe) is False

            # The transaction-scoped lock is released only when its owner
            # commits or rolls back, not when another process-local lock exits.
            await first.commit()
            assert await second.scalar(probe) is True
            await second.rollback()
