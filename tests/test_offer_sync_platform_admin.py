from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, Offer, Workspace


async def _setup(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with sessions() as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    workspace_id = "global-offer-sync-workspace"
    async with sessions() as db:
        db.add(Workspace(id=workspace_id, name="Offer sync audit workspace", slug="offer-sync-audit"))
        await db.commit()
    return engine, sessions, workspace_id


def _override_user(monkeypatch, *, platform_admin: bool, workspace_id: str | None):
    async def current_user():
        return {
            "email": "offer-operator@example.invalid",
            "user_id": "offer-operator",
            "workspace_id": workspace_id,
            "workspace_role": "owner" if platform_admin else "member",
            "is_admin": platform_admin,
        }
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, current_user)


def test_workspace_member_cannot_trigger_global_offer_sync(monkeypatch):
    _override_user(monkeypatch, platform_admin=False, workspace_id="member-workspace")
    calls = []

    async def fake_fetch_programs(**kwargs):
        calls.append(kwargs)
        return {"data": [], "registry_total": 0}

    monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fake_fetch_programs)
    with TestClient(main.app) as client:
        response = client.post("/api/offers/sync")
    assert response.status_code == 403
    assert "Platform Super Admin" in response.text
    assert calls == []


def test_platform_admin_without_workspace_cannot_sync_global_offer_registry(monkeypatch):
    _override_user(monkeypatch, platform_admin=True, workspace_id=None)
    calls = []

    async def fake_fetch_programs(**kwargs):
        calls.append(kwargs)
        return {"data": [], "registry_total": 0}

    monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fake_fetch_programs)
    with TestClient(main.app) as client:
        response = client.post("/api/offers/sync")
    assert response.status_code == 403
    assert calls == []


@pytest.mark.asyncio
async def test_platform_admin_sync_updates_global_catalog_and_writes_audit(monkeypatch):
    engine, sessions, workspace_id = await _setup(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)
        calls = []

        async def fake_fetch_programs(**kwargs):
            calls.append(kwargs)
            return {
                "data": [{
                    "slug": "verified-test-offer",
                    "name": "Example partnership",
                    "url": "https://merchant.example/partner",
                    "category": "creator-tools",
                    "description": "Provider supplied description",
                    "reward_type": "percentage",
                    "reward_value": "12",
                    "cookie_days": 30,
                    "traffic_score": None,
                    "stars_count": 4.5,
                    "verified": False,
                    "raw": {"source_url": "https://provider.example/offers/verified-test-offer"},
                    "tags": ["creator"],
                }],
                "registry_total": 1,
            }

        monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fake_fetch_programs)
        with TestClient(main.app) as client:
            response = client.post("/api/offers/sync?q=creator&limit=10")
        assert response.status_code == 200, response.text
        assert response.json()["created"] == 1
        assert response.json()["updated"] == 0
        assert calls == [{"q": "creator", "limit": 10}]

        async with sessions() as db:
            offer = await db.scalar(select(Offer).where(
                Offer.network == "openaffiliate",
                Offer.external_id == "verified-test-offer",
            ))
            audit = await db.scalar(select(AuditLog).where(
                AuditLog.action == "offers.sync",
                AuditLog.outcome == "completed",
            ))
        assert offer is not None
        assert offer.name == "Example partnership"
        assert offer.verified is False
        assert audit is not None
        assert audit.workspace_id == workspace_id
        assert audit.details_json == {
            "provider": "openaffiliate",
            "created": 1,
            "updated": 0,
            "registry_total": 1,
            "requested_limit": 10,
            "query_supplied": True,
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_offer_sync_provider_failure_is_audited_and_returns_gateway_error(monkeypatch):
    engine, sessions, workspace_id = await _setup(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)

        async def fail_fetch_programs(**kwargs):
            raise TimeoutError("provider unreachable")

        monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fail_fetch_programs)
        with TestClient(main.app) as client:
            response = client.post("/api/offers/sync")
        assert response.status_code == 502
        async with sessions() as db:
            audit = await db.scalar(select(AuditLog).where(AuditLog.action == "offers.sync"))
        assert audit is not None
        assert audit.workspace_id == workspace_id
        assert audit.outcome == "failed"
        assert audit.details_json["error_type"] == "TimeoutError"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_offer_sync_only_accepts_real_boolean_provider_verification(monkeypatch):
    engine, sessions, workspace_id = await _setup(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)

        provider_rows = [
            {"slug": "verify-bool-true", "name": "Literal boolean true", "verified": True},
            {"slug": "verify-bool-false", "name": "Literal boolean false", "verified": False},
            {"slug": "verify-string-false", "name": "String false", "verified": "false"},
            {"slug": "verify-string-true", "name": "String true", "verified": "true"},
            {"slug": "verify-number-one", "name": "Numeric one", "verified": 1},
            {"slug": "verify-missing", "name": "Missing verification", "verified": None},
        ]

        async def fake_fetch_programs(**kwargs):
            return {"data": provider_rows, "registry_total": len(provider_rows)}

        monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fake_fetch_programs)
        with TestClient(main.app) as client:
            response = client.post("/api/offers/sync?limit=10")

        assert response.status_code == 200, response.text
        async with sessions() as db:
            rows = list((await db.scalars(select(Offer).where(
                Offer.network == "openaffiliate",
                Offer.external_id.in_([item["slug"] for item in provider_rows]),
            ))).all())
        actual = {row.external_id: row.verified for row in rows}
        assert actual == {
            "verify-bool-true": True,
            "verify-bool-false": False,
            "verify-string-false": False,
            "verify-string-true": False,
            "verify-number-one": False,
            "verify-missing": False,
        }
    finally:
        await engine.dispose()
