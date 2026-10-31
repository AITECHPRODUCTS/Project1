from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import (
    AdCampaignPlanRecord,
    AdPerformanceObservation,
    AuditLog,
    Workspace,
)


WORKSPACE_A = "ad-scope-workspace-a"
WORKSPACE_B = "ad-scope-workspace-b"
PLAN_A = "ad-plan-owned-by-a"
PLAN_B = "ad-plan-owned-by-b"


def _user_a():
    return {
        "email": "ad-owner-a@example.invalid",
        "user_id": "ad-owner-a",
        "workspace_id": WORKSPACE_A,
        "workspace_role": "owner",
        "is_admin": False,
    }


def _plan(workspace_id: str, plan_id: str, name: str) -> AdCampaignPlanRecord:
    return AdCampaignPlanRecord(
        workspace_id=workspace_id,
        id=plan_id,
        campaign_name=name,
        niche="creator tools",
        audience="independent creators",
        region="US",
        objective="sales",
        platforms_json=["meta"],
        plan_json={
            "plan_id": plan_id,
            "platform_plans": [{"platform": "meta", "creatives": [{"id": plan_id + "-creative"}]}],
        },
        daily_budget_usd=Decimal("10.00"),
        status="draft",
    )


def _observation(workspace_id: str, plan_id: str, creative_id: str) -> AdPerformanceObservation:
    return AdPerformanceObservation(
        workspace_id=workspace_id,
        campaign_plan_id=plan_id,
        platform="meta",
        creative_id=creative_id,
        source_type="manual_report",
        impressions=100,
        clicks=5,
        conversions=1,
        spend_usd=Decimal("2.00"),
        commission_usd=Decimal("3.00"),
        currency="USD",
        evidence_status="operator_supplied_unverified",
        observed_at=datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc),
        note="Tenant-isolation regression fixture",
    )


def test_ad_routes_explicitly_scope_reads_and_writes_when_ambient_scope_is_absent(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add_all([
                Workspace(id=WORKSPACE_A, name="Ad Workspace A", slug="ad-workspace-a"),
                Workspace(id=WORKSPACE_B, name="Ad Workspace B", slug="ad-workspace-b"),
                _plan(WORKSPACE_A, PLAN_A, "Private Plan A"),
                _plan(WORKSPACE_B, PLAN_B, "Private Plan B"),
                _observation(WORKSPACE_A, PLAN_A, "private-creative-a"),
                _observation(WORKSPACE_B, PLAN_B, "private-creative-b"),
            ])
            await db.commit()

    async def override_session():
        async with sessions() as db:
            yield db

    async def authenticated_workspace_a():
        return _user_a()

    asyncio.run(prepare_database())
    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, authenticated_workspace_a)
    client = TestClient(main.app)
    try:
        # The test auth dependency supplies a workspace, but no signed session cookie
        # is set, so WorkspaceContextMiddleware leaves the ambient ContextVar unset.
        plan_list = client.get("/api/ads/plans?limit=20")
        assert plan_list.status_code == 200, plan_list.text
        assert {item["id"] for item in plan_list.json()["data"]} == {PLAN_A}

        own_plan = client.get(f"/api/ads/plans/{PLAN_A}")
        foreign_plan = client.get(f"/api/ads/plans/{PLAN_B}")
        assert own_plan.status_code == 200, own_plan.text
        assert foreign_plan.status_code == 404, foreign_plan.text

        observation_list = client.get("/api/ads/observations?limit=100")
        assert observation_list.status_code == 200, observation_list.text
        assert {item["creative_id"] for item in observation_list.json()["data"]} == {"private-creative-a"}

        performance = client.get("/api/ads/performance?limit=100")
        assert performance.status_code == 200, performance.text
        assert {item["creative_id"] for item in performance.json()["items"]} == {"private-creative-a"}

        # A workspace-A operator may not attach a report to workspace-B's plan.
        cross_workspace_link = client.post("/api/ads/observations", json={
            "campaign_plan_id": PLAN_B,
            "platform": "meta",
            "creative_id": "attempted-cross-tenant-link",
            "source_type": "manual_report",
            "impressions": 1,
            "clicks": 1,
            "conversions": 0,
            "spend_usd": "1.00",
            "commission_usd": "0.00",
        })
        assert cross_workspace_link.status_code == 404, cross_workspace_link.text

        # New drafts/reports and their audit evidence are explicitly assigned to
        # the authenticated workspace rather than silently relying on ContextVars.
        new_plan = client.post("/api/ads/plan", json={
            "campaign_name": "Workspace A explicit plan",
            "niche": "creator productivity",
            "audience": "small publishers",
            "region": "US",
            "objective": "sales",
            "platforms": ["meta"],
            "variants_per_platform": 1,
            "daily_budget_usd": "5.00",
            "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
        })
        assert new_plan.status_code == 201, new_plan.text
        new_plan_id = new_plan.json()["plan_id"]

        new_observation = client.post("/api/ads/observations", json={
            "platform": "meta",
            "creative_id": "explicit-workspace-a-observation",
            "source_type": "manual_report",
            "impressions": 8,
            "clicks": 2,
            "conversions": 0,
            "spend_usd": "1.00",
            "commission_usd": "0.00",
        })
        assert new_observation.status_code == 201, new_observation.text
        new_observation_id = new_observation.json()["id"]

        async def inspect_persisted_rows():
            async with sessions() as db:
                plan = await db.get(AdCampaignPlanRecord, new_plan_id)
                observation = await db.get(AdPerformanceObservation, new_observation_id)
                plan_audit = await db.scalar(select(AuditLog).where(
                    AuditLog.action == "ads.plan.created",
                    AuditLog.resource_id == new_plan_id,
                ))
                observation_audit = await db.scalar(select(AuditLog).where(
                    AuditLog.action == "ads.performance_observation.created",
                    AuditLog.resource_id == new_observation_id,
                ))
            return plan, observation, plan_audit, observation_audit

        plan, observation, plan_audit, observation_audit = asyncio.run(inspect_persisted_rows())
        assert plan is not None and plan.workspace_id == WORKSPACE_A
        assert observation is not None and observation.workspace_id == WORKSPACE_A
        assert plan_audit is not None and plan_audit.workspace_id == WORKSPACE_A
        assert observation_audit is not None and observation_audit.workspace_id == WORKSPACE_A
        assert observation.evidence_status == "operator_supplied_unverified"
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())
