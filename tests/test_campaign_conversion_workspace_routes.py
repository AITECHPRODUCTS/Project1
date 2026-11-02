from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from urllib.parse import parse_qs, urlparse

from backend import main
from backend.database import Base, get_session
from backend.models import Campaign, Conversion, ConversionLedgerEntry, Workspace
from backend.tenancy import reset_workspace_id, set_workspace_id, workspace_scope


async def _database(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with sessions() as session:
            yield session

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    return engine, sessions


def test_campaign_and_conversion_routes_deny_users_without_workspace(monkeypatch):
    async def no_workspace():
        return {
            "email": "unscoped@example.invalid",
            "user_id": "unscoped-campaign-user",
            "workspace_id": None,
            "workspace_role": "member",
            "is_admin": False,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    client = TestClient(main.app)
    responses = [
        client.get("/api/campaigns"),
        client.post("/api/campaigns", json={
            "name": "No workspace campaign",
            "niche": "testing",
            "primary_destination": "https://example.com/offer",
        }),
        client.post("/api/campaigns/not-real/health"),
        client.post("/api/analytics/conversions", json={
            "network": "test-network",
            "external_event_id": "unscoped-event",
            "revenue": "10.00",
            "commission": "1.00",
        }),
    ]
    assert [response.status_code for response in responses] == [403] * len(responses)


@pytest.mark.asyncio
async def test_campaign_and_conversion_routes_are_bound_to_selected_workspace(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        async with sessions() as db:
            workspace_a = Workspace(name="Campaign Route A", slug="campaign-route-a")
            workspace_b = Workspace(name="Campaign Route B", slug="campaign-route-b")
            db.add_all([workspace_a, workspace_b])
            await db.flush()
            a_id, b_id = workspace_a.id, workspace_b.id
            await db.commit()

        async with sessions() as db:
            with workspace_scope(a_id):
                campaign_a = Campaign(
                    workspace_id=a_id,
                    name="Tenant A campaign",
                    niche="testing",
                    primary_destination="https://tenant-a.example/offer",
                )
                db.add(campaign_a)
                await db.commit()
        async with sessions() as db:
            with workspace_scope(b_id):
                campaign_b = Campaign(
                    workspace_id=b_id,
                    name="Tenant B campaign",
                    niche="testing",
                    primary_destination="https://tenant-b.example/offer",
                )
                db.add(campaign_b)
                db.add(Conversion(
                    workspace_id=b_id,
                    network="test-network",
                    external_event_id="shared-event-id",
                    revenue=10.0,
                    commission=1.0,
                    currency="USD",
                    status="approved",
                ))
                await db.commit()
                campaign_b_id = campaign_b.id

        async def auth_workspace_a():
            token = set_workspace_id(a_id)
            try:
                yield {
                    "email": "tenant-a@example.invalid",
                    "user_id": "tenant-a-user",
                    "workspace_id": a_id,
                    "workspace_role": "owner",
                    "is_admin": False,
                }
            finally:
                reset_workspace_id(token)

        monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, auth_workspace_a)
        client = TestClient(main.app)

        listed = client.get("/api/campaigns")
        assert listed.status_code == 200
        assert [row["name"] for row in listed.json()["data"]] == ["Tenant A campaign"]

        cross_tenant_health = client.post(f"/api/campaigns/{campaign_b_id}/health")
        assert cross_tenant_health.status_code == 404

        converted = client.post("/api/analytics/conversions", json={
            "network": "test-network",
            "external_event_id": "shared-event-id",
            "revenue": "20.00",
            "commission": "2.00",
            "currency": "USD",
            "status": "approved",
        })
        assert converted.status_code == 200
        assert converted.json()["status"] == "recorded"

        with workspace_scope(a_id):
            async with sessions() as db:
                own_conversion = await db.scalar(select(Conversion).where(
                    Conversion.workspace_id == a_id,
                    Conversion.network == "test-network",
                    Conversion.external_event_id == "shared-event-id",
                ))
                own_ledger = await db.scalar(select(ConversionLedgerEntry).where(
                    ConversionLedgerEntry.workspace_id == a_id,
                    ConversionLedgerEntry.network == "test-network",
                    ConversionLedgerEntry.external_event_id == "shared-event-id",
                ))
        assert own_conversion is not None and own_conversion.revenue == pytest.approx(20.0)
        assert own_ledger is not None and own_ledger.workspace_id == a_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tid_campaign_redirect_overwrites_existing_tid_with_local_click_id(monkeypatch):
    engine,sessions=await _database(monkeypatch)
    try:
        async with sessions() as db:
            workspace=Workspace(name="ClickBank TID route",slug="clickbank-tid-route")
            db.add(workspace);await db.flush()
            campaign=Campaign(workspace_id=workspace.id,name="ClickBank TID",niche="software",
                primary_destination="https://hop.clickbank.net/?affiliate=creator&vendor=merchant&tid=old_value",
                tracking_parameter="tid")
            db.add(campaign);await db.commit();campaign_id=campaign.id
        expected="d"*32
        async def fake_record(session,campaign,*,user_agent="",utm=None):
            assert campaign.tracking_parameter=="tid"
            assert utm=={"utm_source":"newsletter"}
            return {"destination":campaign.primary_destination,"route":"primary","status_code":200,
                "primary_healthy":True,"fallback_healthy":None,"health_error":None,
                "click_id":expected,"campaign_id":campaign.id}
        monkeypatch.setattr(main,"record_click_and_resolve",fake_record)
        client=TestClient(main.app)
        with client:
            response=client.get(f"/r/{campaign_id}?utm_source=newsletter",follow_redirects=False)
        assert response.status_code==302
        assert parse_qs(urlparse(response.headers["location"]).query)["tid"]==[expected]
    finally:
        await engine.dispose()

