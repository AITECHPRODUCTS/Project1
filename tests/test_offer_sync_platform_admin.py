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
        status_response = client.get("/api/integrations/openaffiliate/sync-status")
        history_response = client.get("/api/integrations/openaffiliate/sync-history")
    assert response.status_code == 403
    assert status_response.status_code == 403
    assert history_response.status_code == 403
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
        status_response = client.get("/api/integrations/openaffiliate/sync-status")
        history_response = client.get("/api/integrations/openaffiliate/sync-history")
    assert response.status_code == 403
    assert status_response.status_code == 403
    assert history_response.status_code == 403
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
            status_response = client.get("/api/integrations/openaffiliate/sync-status")
        assert response.status_code == 200, response.text
        assert status_response.status_code == 200, status_response.text
        status_payload = status_response.json()
        assert status_payload["state"] == "completed"
        assert status_payload["created"] == 1
        assert status_payload["updated"] == 0
        assert status_payload["registry_total"] == 1
        assert status_payload["requested_limit"] == 10
        assert status_payload["query_supplied"] is True
        assert status_payload["source_attestation_verified"] is False
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
            status_response = client.get("/api/integrations/openaffiliate/sync-status")
        assert response.status_code == 502
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["state"] == "failed"
        assert status_response.json()["error_type"] == "TimeoutError"
        assert "provider unreachable" not in status_response.text
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


@pytest.mark.asyncio
async def test_platform_admin_sync_status_is_unknown_before_first_attempt(monkeypatch):
    engine, sessions, workspace_id = await _setup(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)
        with TestClient(main.app) as client:
            response = client.get("/api/integrations/openaffiliate/sync-status")
            history = client.get("/api/integrations/openaffiliate/sync-history")
            invalid_low = client.get("/api/integrations/openaffiliate/sync-history?limit=0")
            invalid_high = client.get("/api/integrations/openaffiliate/sync-history?limit=51")
        assert response.status_code == 200, response.text
        assert history.status_code == 200, history.text
        assert history.json()["count"] == 0
        assert history.json()["items"] == []
        assert history.json()["source_attestation_verified"] is False
        assert invalid_low.status_code == 422
        assert invalid_high.status_code == 422
        assert response.json()["state"] == "never_synced"
        assert response.json()["last_attempt_at"] is None
        assert response.json()["created"] is None
        assert response.json()["source_attestation_verified"] is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_openaffiliate_sync_status_is_scoped_to_active_workspace(monkeypatch):
    engine, sessions, workspace_a = await _setup(monkeypatch)
    workspace_b = "different-sync-status-workspace"
    try:
        async with sessions() as db:
            db.add(Workspace(id=workspace_b, name="Workspace B", slug="sync-status-workspace-b"))
            await db.commit()

        async def fake_fetch_programs(*, q: str | None = None, limit: int = 100):
            return {"data": [], "registry_total": 99 if q else 7}

        monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fake_fetch_programs)

        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_a)
        with TestClient(main.app) as client:
            first = client.post("/api/offers/sync")
        assert first.status_code == 200, first.text

        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_b)
        with TestClient(main.app) as client:
            second = client.post("/api/offers/sync?q=workspace-b")
        assert second.status_code == 200, second.text

        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_a)
        with TestClient(main.app) as client:
            response = client.get("/api/integrations/openaffiliate/sync-status")
            history = client.get("/api/integrations/openaffiliate/sync-history?limit=10")
        assert response.status_code == 200, response.text
        assert response.json()["registry_total"] == 7
        assert response.json()["query_supplied"] is False
        assert response.json()["state"] == "completed"
        assert history.status_code == 200, history.text
        assert history.json()["count"] == 1
        assert history.json()["items"][0]["registry_total"] == 7
        assert history.json()["items"][0]["source_attestation_verified"] is False

        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_b)
        with TestClient(main.app) as client:
            other_history = client.get("/api/integrations/openaffiliate/sync-history")
        assert other_history.status_code == 200, other_history.text
        assert other_history.json()["count"] == 1
        assert other_history.json()["items"][0]["registry_total"] == 99
    finally:
        await engine.dispose()



@pytest.mark.asyncio
async def test_openaffiliate_sync_history_is_newest_first_bounded_and_sanitized(monkeypatch):
    engine, sessions, workspace_id = await _setup(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)

        async def fake_fetch_programs(*, q: str | None = None, limit: int = 100):
            if q == "failure":
                raise TimeoutError("provider private response body must never be exposed")
            return {"data": [], "registry_total": 9 if q == "latest" else 7}

        monkeypatch.setattr(main.openaffiliate_client, "fetch_programs", fake_fetch_programs)
        with TestClient(main.app) as client:
            first = client.post("/api/offers/sync?limit=5")
            failed = client.post("/api/offers/sync?q=failure")
            latest = client.post("/api/offers/sync?q=latest")
        assert first.status_code == 200, first.text
        assert failed.status_code == 502
        assert latest.status_code == 200, latest.text

        # Fix timestamps deterministically so the assertion checks ordering rather
        # than depending on DB timestamp precision or randomly generated row IDs.
        async with sessions() as db:
            audits = list((await db.scalars(select(AuditLog).where(
                AuditLog.workspace_id == workspace_id,
                AuditLog.action == "offers.sync",
                AuditLog.resource_type == "offer_registry",
            ))).all())
            for audit in audits:
                details = audit.details_json if isinstance(audit.details_json, dict) else {}
                if audit.outcome == "failed":
                    audit.created_at = datetime(2026, 10, 2, tzinfo=timezone.utc)
                elif details.get("registry_total") == 7:
                    audit.created_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
                elif details.get("registry_total") == 9:
                    audit.created_at = datetime(2026, 10, 3, tzinfo=timezone.utc)
            await db.commit()

        with TestClient(main.app) as client:
            response = client.get("/api/integrations/openaffiliate/sync-history?limit=2")
            all_history = client.get("/api/integrations/openaffiliate/sync-history?limit=50")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["count"] == 2
        assert payload["limit"] == 2
        assert [item["state"] for item in payload["items"]] == ["completed", "failed"]
        assert payload["items"][0]["registry_total"] == 9
        assert payload["items"][1]["error_type"] == "TimeoutError"
        assert payload["items"][1]["source_attestation_verified"] is False
        assert "provider private response body" not in response.text
        assert payload["source_attestation_verified"] is False

        assert all_history.status_code == 200, all_history.text
        assert all_history.json()["count"] == 3
        assert all_history.json()["items"][0]["registry_total"] == 9
        assert all_history.json()["items"][1]["state"] == "failed"
        assert all_history.json()["items"][2]["registry_total"] == 7
    finally:
        await engine.dispose()
