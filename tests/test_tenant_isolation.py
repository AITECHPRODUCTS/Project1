from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import Campaign, Workspace
from backend.tenancy import workspace_scope


async def _make_workspace(db, name: str, slug: str) -> Workspace:
    workspace = Workspace(name=name, slug=slug)
    db.add(workspace)
    await db.flush()
    return workspace


@pytest.mark.asyncio
async def test_campaign_rows_are_filtered_and_new_rows_inherit_active_workspace():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            a = await _make_workspace(db, "Workspace A", "tenant-test-a")
            b = await _make_workspace(db, "Workspace B", "tenant-test-b")
            await db.commit()
            workspace_a_id, workspace_b_id = a.id, b.id

        with workspace_scope(workspace_a_id):
            async with sessions() as db:
                campaign_a = Campaign(
                    name="A campaign",
                    niche="fitness",
                    primary_destination="https://example.com/a",
                )
                db.add(campaign_a)
                await db.commit()
                campaign_a_id = campaign_a.id
                assert campaign_a.workspace_id == workspace_a_id

        with workspace_scope(workspace_b_id):
            async with sessions() as db:
                campaign_b = Campaign(
                    name="B campaign",
                    niche="travel",
                    primary_destination="https://example.com/b",
                )
                db.add(campaign_b)
                await db.commit()
                campaign_b_id = campaign_b.id
                assert campaign_b.workspace_id == workspace_b_id
                assert await db.get(Campaign, campaign_a_id) is None
                rows = list((await db.scalars(select(Campaign))).all())
                assert [x.id for x in rows] == [campaign_b_id]

        with workspace_scope(workspace_a_id):
            async with sessions() as db:
                assert await db.get(Campaign, campaign_a_id) is not None
                assert await db.get(Campaign, campaign_b_id) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_scoped_production_writes_fail_closed_without_workspace(monkeypatch):
    import backend.database as database

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(database.settings, "app_env", "production")
        with workspace_scope(None):
            async with sessions() as db:
                db.add(
                    Campaign(
                        name="Unscoped attempt",
                        niche="finance",
                        primary_destination="https://example.com",
                    )
                )
                with pytest.raises(RuntimeError, match="workspace context"):
                    await db.flush()
                await db.rollback()
    finally:
        await engine.dispose()


def test_registered_accounts_do_not_default_to_platform_admin():
    from backend.models import UserAccount

    account = UserAccount(email="least-privilege@example.test", password_hash="hashed")
    assert account.is_admin is False
