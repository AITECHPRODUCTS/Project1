from __future__ import annotations

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.core.errors import ResourceBudgetExceeded
from backend.database import engine
from backend.models import ResourceUsage, Workspace
from backend.services import resource_budget
from backend.tenancy import workspace_scope

_acquire_workspace_budget_lock = resource_budget._acquire_workspace_budget_lock


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

    test_engine = create_async_engine(engine.url.render_as_string(hide_password=False), pool_pre_ping=True)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    try:
        async with sessions() as first:
            async with sessions() as second:
                await _acquire_workspace_budget_lock(first, workspace_id)
                assert await second.scalar(probe) is False

                # The transaction-scoped lock is released only when its owner
                # commits or rolls back, not when another process-local lock exits.
                await first.commit()
                assert await second.scalar(probe) is True
                await second.rollback()
    finally:
        await test_engine.dispose()



@pytest.mark.asyncio
async def test_postgres_concurrent_reservations_cannot_overspend_workspace_budget(monkeypatch):
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL resource-budget integration job")

    # Simulate two independent application processes: each module instance has
    # its own asyncio lock, while both share only the PostgreSQL database.
    spec = importlib.util.spec_from_file_location(
        "resource_budget_replica",
        Path(resource_budget.__file__),
    )
    assert spec is not None and spec.loader is not None
    replica = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replica)
    test_engine = create_async_engine(engine.url.render_as_string(hide_password=False), pool_pre_ping=True)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(resource_budget, "SessionLocal", sessions)
    replica.SessionLocal = sessions

    settings = get_settings()
    monkeypatch.setattr(settings, "resource_budget_usd_per_day", 1.5)
    monkeypatch.setattr(settings, "resource_budget_usd_per_niche", 1.5)

    workspace_id = None
    try:
        async with sessions() as db:
            workspace = Workspace(
                name="Resource budget concurrency",
                slug=f"resource-budget-{uuid.uuid4().hex}",
            )
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id

        async def reserve_from(module):
            with workspace_scope(workspace_id):
                return await module.reserve(
                    "shared-niche",
                    "remote-test-provider",
                    "test-model",
                    1_000_000,
                    0,
                    workspace_id=workspace_id,
                )

        results = await asyncio.gather(
            reserve_from(resource_budget),
            reserve_from(replica),
            return_exceptions=True,
        )
        successes = [value for value in results if isinstance(value, str)]
        failures = [value for value in results if isinstance(value, BaseException)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], ResourceBudgetExceeded)

        with workspace_scope(workspace_id):
            async with sessions() as db:
                count, total = (
                    await db.execute(
                        select(
                            func.count(ResourceUsage.id),
                            func.coalesce(func.sum(ResourceUsage.estimated_cost_usd), 0.0),
                        ).where(ResourceUsage.workspace_id == workspace_id)
                    )
                ).one()
        assert count == 1
        assert float(total) == pytest.approx(1.0)
    finally:
        try:
            if workspace_id:
                async with sessions() as db:
                    await db.execute(
                        delete(ResourceUsage).where(ResourceUsage.workspace_id == workspace_id)
                    )
                    await db.execute(delete(Workspace).where(Workspace.id == workspace_id))
                    await db.commit()
        finally:
            await test_engine.dispose()
