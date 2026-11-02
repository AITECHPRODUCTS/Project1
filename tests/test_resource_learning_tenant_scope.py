from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base
from backend.models import Campaign, ClickEvent, Conversion, ConversionLedgerEntry, ResourceUsage, Workspace
from backend.services import resource_budget, s6_s8_analytics
from backend.tenancy import workspace_scope


async def _database(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(resource_budget, "SessionLocal", sessions)
    monkeypatch.setattr(s6_s8_analytics, "SessionLocal", sessions)
    return engine, sessions


@pytest.mark.asyncio
async def test_resource_budget_helpers_fail_closed_without_workspace():
    with workspace_scope(None):
        with pytest.raises(ValueError, match="Authorized workspace context"):
            await resource_budget.status()
        with pytest.raises(ValueError, match="Authorized workspace context"):
            await resource_budget.reserve("niche", "provider", "model", 100, 100)
        with pytest.raises(ValueError, match="Authorized workspace context"):
            await resource_budget.finalize("missing-reservation", 10, 10)


@pytest.mark.asyncio
async def test_resource_budget_status_returns_only_active_workspace_usage(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        async with sessions() as db:
            workspace_a = Workspace(name="Budget Workspace A", slug="budget-tenant-a")
            workspace_b = Workspace(name="Budget Workspace B", slug="budget-tenant-b")
            db.add_all([workspace_a, workspace_b])
            await db.flush()
            workspace_a_id, workspace_b_id = workspace_a.id, workspace_b.id
            await db.commit()

        now = datetime.now(timezone.utc)
        for workspace_id, niche, cost in (
            (workspace_a_id, "private-a-niche", 0.25),
            (workspace_b_id, "private-b-niche", 8.75),
        ):
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    db.add(
                        ResourceUsage(
                            workspace_id=workspace_id,
                            niche=niche,
                            provider="test-provider",
                            model="test-model",
                            estimated_cost_usd=cost,
                            status="completed",
                            created_at=now,
                        )
                    )
                    await db.commit()

        result = await resource_budget.status(workspace_id=workspace_a_id)
        assert result["workspace_id"] == workspace_a_id
        assert result["daily_estimated_used_usd"] == pytest.approx(0.25)
        assert result["niche_estimated_used_usd"] == {"private-a-niche": pytest.approx(0.25)}
        assert "private-b-niche" not in result["niche_estimated_used_usd"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_self_learning_requires_and_respects_workspace_scope(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        async with sessions() as db:
            workspace_a = Workspace(name="Learning Workspace A", slug="learning-tenant-a")
            workspace_b = Workspace(name="Learning Workspace B", slug="learning-tenant-b")
            db.add_all([workspace_a, workspace_b])
            await db.flush()
            workspace_a_id, workspace_b_id = workspace_a.id, workspace_b.id
            await db.commit()

        now = datetime.now(timezone.utc)
        for workspace_id, external_event, hook in (
            (workspace_a_id, "shared-event-id", "private-a-hook"),
            (workspace_b_id, "shared-event-id", "private-b-hook"),
        ):
            with workspace_scope(workspace_id):
                async with sessions() as db:
                    db.add(
                        Conversion(
                            workspace_id=workspace_id,
                            network="test-network",
                            external_event_id=external_event,
                            commission=1.25,
                            revenue=10.0,
                            hook=hook,
                            status="approved",
                            created_at=now,
                        )
                    )
                    await db.commit()

        with workspace_scope(None):
            with pytest.raises(ValueError, match="Authorized workspace context"):
                await s6_s8_analytics.self_improver_loop()

        result = await s6_s8_analytics.self_improver_loop(workspace_id=workspace_a_id)
        assert result["conversions_scanned"] == 1
        assert result["clicks_scanned"] == 0
        assert result["learned_hooks"] == []
    finally:
        await engine.dispose()


def test_resource_and_learning_routes_deny_users_without_workspace(monkeypatch):
    async def no_workspace():
        return {
            "email": "unscoped@example.invalid",
            "user_id": "unscoped-test-user",
            "workspace_id": None,
            "workspace_role": "member",
            "is_admin": False,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    client = TestClient(main.app)
    responses = [
        client.get("/api/resource-budget"),
        client.post("/api/analytics/self-improve"),
    ]
    assert [response.status_code for response in responses] == [403, 403]


@pytest.mark.asyncio
async def test_postgres_resource_budget_lock_is_namespaced_and_workspace_scoped():
    from sqlalchemy.dialects import postgresql

    class FakeBind:
        dialect = type("Dialect", (), {"name": "postgresql"})()

    class FakeSession:
        def __init__(self):
            self.statement = None

        def get_bind(self):
            return FakeBind()

        async def execute(self, statement):
            self.statement = statement

    first = FakeSession()
    await resource_budget._acquire_workspace_budget_lock(first, "workspace-a")
    assert first.statement is not None
    compiled = first.statement.compile(dialect=postgresql.dialect())
    assert "pg_advisory_xact_lock" in str(compiled)
    assert "omni-affiliate-os/resource-budget/v1" in compiled.params.values()
    assert "workspace-a" in compiled.params.values()

    second = FakeSession()
    await resource_budget._acquire_workspace_budget_lock(second, "workspace-b")
    second_compiled = second.statement.compile(dialect=postgresql.dialect())
    assert "workspace-b" in second_compiled.params.values()
    assert compiled.params != second_compiled.params


@pytest.mark.asyncio
async def test_non_postgres_resource_budget_lock_does_not_issue_advisory_sql():
    class FakeBind:
        dialect = type("Dialect", (), {"name": "sqlite"})()

    class FakeSession:
        def __init__(self):
            self.executed = False

        def get_bind(self):
            return FakeBind()

        async def execute(self, statement):
            self.executed = True

    db = FakeSession()
    await resource_budget._acquire_workspace_budget_lock(db, "workspace-a")
    assert db.executed is False



@pytest.mark.asyncio
async def test_learning_uses_net_commission_for_partial_refunds_and_excludes_full_reversals(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    settings = main.get_settings()
    monkeypatch.setattr(settings, "min_conversions_for_learning", 1)
    monkeypatch.setattr(settings, "min_hook_conversion_rate", 0.0)
    workspace_id = None
    try:
        async with sessions() as db:
            workspace = Workspace(name="Learning Reversal Workspace", slug="learning-reversal-tenant")
            db.add(workspace)
            await db.flush()
            workspace_id = workspace.id
            with workspace_scope(workspace_id):
                campaign = Campaign(
                    name="Learning reversal campaign",
                    niche="test",
                    primary_destination="https://example.invalid/offer",
                )
                db.add(campaign)
                await db.flush()
                db.add(ClickEvent(
                    click_id="learning-reversal-click",
                    campaign_id=campaign.id,
                    destination_url="https://example.invalid/offer",
                    chosen_destination="primary",
                    utm_json={"utm_content": "partial-refund-hook"},
                ))
                db.add_all([
                    Conversion(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="partial-original",
                        commission=1.25,
                        revenue=10.0,
                        hook="partial-refund-hook",
                        status="partially_reversed",
                        event_json={"reversal": False},
                    ),
                    Conversion(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="partial-event",
                        commission=-0.50,
                        revenue=-2.0,
                        hook="partial-refund-hook",
                        status="partially_reversed",
                        event_json={"reversal": True, "partial_reversal": True},
                    ),
                    Conversion(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="fully-reversed-original",
                        commission=5.0,
                        revenue=50.0,
                        hook="partial-refund-hook",
                        status="reversed",
                        event_json={"reversal": False},
                    ),
                ])
                db.add_all([
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="partial-original",
                        entry_type="conversion",
                        commission_amount=Decimal("1.250000"),
                        revenue_amount=Decimal("10.000000"),
                        currency="USD",
                        status="partially_reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="partial-event",
                        entry_type="reversal",
                        original_event_id="partial-original",
                        commission_amount=Decimal("-0.500000"),
                        revenue_amount=Decimal("-2.000000"),
                        currency="USD",
                        status="partially_reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="fully-reversed-original",
                        entry_type="conversion",
                        commission_amount=Decimal("5.000000"),
                        revenue_amount=Decimal("50.000000"),
                        currency="USD",
                        status="reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                    ConversionLedgerEntry(
                        workspace_id=workspace_id,
                        network="learning-test-network",
                        external_event_id="fully-reversed-event",
                        entry_type="reversal",
                        original_event_id="fully-reversed-original",
                        commission_amount=Decimal("-5.000000"),
                        revenue_amount=Decimal("-50.000000"),
                        currency="USD",
                        status="reversed",
                        evidence_status="signed_webhook_verified",
                        source_event_json={"test_fixture": True},
                    ),
                ])
                await db.commit()

        result = await s6_s8_analytics.self_improver_loop(workspace_id=workspace_id)
        assert result["conversions_scanned"] == 1
        assert result["performance_memory_candidates_saved"] == 1
        assert result["learned_hooks"][0]["hook"] == "partial-refund-hook"
        assert result["learned_hooks"][0]["conversions"] == 1
        assert result["learned_hooks"][0]["commission"] == pytest.approx(0.75)
    finally:
        await engine.dispose()
