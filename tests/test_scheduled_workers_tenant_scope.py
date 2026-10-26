from __future__ import annotations

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import pytest

from backend import main
from backend.database import Base
from backend.models import Campaign, PayoutThreshold, Workspace
from backend.tenancy import get_workspace_id, workspace_scope


async def _database(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    return engine, sessions


async def _workspaces(sessions):
    async with sessions() as db:
        a = Workspace(name="Worker Workspace A", slug="worker-tenant-a")
        b = Workspace(name="Worker Workspace B", slug="worker-tenant-b")
        db.add_all([a, b])
        await db.flush()
        ids = (a.id, b.id)
        await db.commit()
    return ids


@pytest.mark.asyncio
async def test_campaign_health_worker_runs_inside_each_workspace(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        a_id, b_id = await _workspaces(sessions)
        for workspace_id, destination in ((a_id, "https://tenant-a.example"), (b_id, "https://tenant-b.example")):
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    db.add(Campaign(
                        workspace_id=workspace_id,
                        name=f"Campaign {workspace_id[:6]}",
                        niche="testing",
                        primary_destination=destination,
                        is_active=True,
                    ))
                    await db.commit()

        seen: list[tuple[str | None, str]] = []

        async def healthy(url: str):
            seen.append((get_workspace_id(), url))
            return True, 200, None

        monkeypatch.setattr(main, "destination_healthy", healthy)
        await main.campaign_health_job()

        assert set(seen) == {(a_id, "https://tenant-a.example"), (b_id, "https://tenant-b.example")}
        for workspace_id in (a_id, b_id):
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    campaign = await db.scalar(select(Campaign))
                    assert campaign is not None and campaign.primary_healthy is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_email_worker_passes_workspace_identity_to_delivery(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        a_id, b_id = await _workspaces(sessions)
        captured: list[tuple[str | None, str | None]] = []

        async def fake_send_due_emails(session=None, *, limit=50, workspace_id=None):
            captured.append((workspace_id, get_workspace_id()))
            return {"sent": 0, "attempted": 0, "skipped": 0}

        monkeypatch.setattr(main, "send_due_emails", fake_send_due_emails)
        await main.email_job()

        assert set(captured) == {(a_id, a_id), (b_id, b_id)}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_threshold_worker_queries_each_workspace_under_scope(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    seen: list[str | None] = []

    def capture_scope(execute_state):
        statement = str(execute_state.statement).lower()
        if execute_state.is_select and "payout_thresholds" in statement:
            seen.append(get_workspace_id())

    try:
        a_id, b_id = await _workspaces(sessions)
        for workspace_id in (a_id, b_id):
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    db.add(PayoutThreshold(
                        workspace_id=workspace_id,
                        network=f"network-{workspace_id[:6]}",
                        currency="USD",
                        minimum_threshold=10.0,
                        reported_balance=12.0,
                    ))
                    await db.commit()

        event.listen(Session, "do_orm_execute", capture_scope)
        try:
            await main.threshold_job()
        finally:
            event.remove(Session, "do_orm_execute", capture_scope)

        assert {value for value in seen if value} == {a_id, b_id}
        for workspace_id in (a_id, b_id):
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    row = await db.scalar(select(PayoutThreshold))
                    assert row is not None and row.threshold_reached is True
    finally:
        await engine.dispose()
