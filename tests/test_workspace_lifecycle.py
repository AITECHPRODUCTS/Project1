from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, Workspace


ADMIN_WORKSPACE = "10000000-0000-4000-8000-000000000001"
TARGET_WORKSPACE = "10000000-0000-4000-8000-000000000002"


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
    async with sessions() as db:
        db.add_all([
            Workspace(id=ADMIN_WORKSPACE, name="Platform operations", slug="platform-operations"),
            Workspace(id=TARGET_WORKSPACE, name="Demo affiliate tenant", slug="demo-affiliate-tenant"),
        ])
        await db.commit()
    return engine, sessions


def _as_user(monkeypatch, *, is_admin=True, workspace_id=ADMIN_WORKSPACE):
    async def current_user():
        return {
            "email": "platform.operator@example.invalid",
            "user_id": "platform-operator",
            "workspace_id": workspace_id,
            "workspace_role": "owner",
            "is_admin": is_admin,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, current_user)


@pytest.mark.asyncio
async def test_tenant_suspension_and_reinstatement_persist_state_and_audit(monkeypatch):
    engine, sessions = await _setup(monkeypatch)
    try:
        _as_user(monkeypatch)
        with TestClient(main.app) as client:
            initial = client.get("/api/admin/tenants?limit=100")
            assert initial.status_code == 200, initial.text
            listing = {row["id"]: row for row in initial.json()["data"]}
            assert listing[TARGET_WORKSPACE]["lifecycle_state"] == "active"
            assert listing[TARGET_WORKSPACE]["active_memberships"] == 0
            assert initial.json()["lifecycle_mutations_available"] is True

            invalid_reason = client.post(
                f"/api/admin/tenants/{TARGET_WORKSPACE}/suspend",
                json={"reason": "    "},
            )
            assert invalid_reason.status_code == 422

            self_suspend = client.post(
                f"/api/admin/tenants/{ADMIN_WORKSPACE}/suspend",
                json={"reason": "Prevent current operator lockout"},
            )
            assert self_suspend.status_code == 409

            suspended_response = client.post(
                f"/api/admin/tenants/{TARGET_WORKSPACE}/suspend",
                json={"reason": "Confirmed abuse after support investigation"},
            )
            assert suspended_response.status_code == 200, suspended_response.text
            suspended_payload = suspended_response.json()
            assert suspended_payload["lifecycle_state"] == "suspended"
            assert suspended_payload["suspended_at"]
            assert suspended_payload["suspended_by"] == "platform.operator@example.invalid"
            assert suspended_payload["suspension_reason"] == "Confirmed abuse after support investigation"

            duplicate = client.post(
                f"/api/admin/tenants/{TARGET_WORKSPACE}/suspend",
                json={"reason": "Duplicate suspension request"},
            )
            assert duplicate.status_code == 409

            reinstate_response = client.post(
                f"/api/admin/tenants/{TARGET_WORKSPACE}/reinstate",
                json={"reason": "Appeal reviewed and access restored"},
            )
            assert reinstate_response.status_code == 200, reinstate_response.text
            restored = reinstate_response.json()
            assert restored["lifecycle_state"] == "active"
            assert restored["suspended_at"] is None
            assert restored["suspended_by"] is None
            assert restored["suspension_reason"] is None

        async with sessions() as db:
            tenant = await db.get(Workspace, TARGET_WORKSPACE)
            audits = list((await db.scalars(
                select(AuditLog)
                .where(
                    AuditLog.workspace_id == TARGET_WORKSPACE,
                    AuditLog.resource_id == TARGET_WORKSPACE,
                    AuditLog.action.in_([
                        "workspace.lifecycle.suspended",
                        "workspace.lifecycle.reinstated",
                    ]),
                )
                .order_by(AuditLog.action.asc())
            )).all())

        assert tenant is not None and tenant.lifecycle_state == "active"
        assert len(audits) == 2
        by_action = {row.action: row for row in audits}
        assert by_action["workspace.lifecycle.suspended"].details_json["reason"] == "Confirmed abuse after support investigation"
        assert by_action["workspace.lifecycle.reinstated"].details_json["reason"] == "Appeal reviewed and access restored"
    finally:
        await engine.dispose()


def test_non_platform_admin_cannot_change_tenant_lifecycle(monkeypatch):
    engine, sessions = asyncio.run(_setup(monkeypatch))
    try:
        _as_user(monkeypatch, is_admin=False, workspace_id=ADMIN_WORKSPACE)
        with TestClient(main.app) as client:
            response = client.post(
                f"/api/admin/tenants/{TARGET_WORKSPACE}/suspend",
                json={"reason": "Confirmed abuse after support investigation"},
            )
        assert response.status_code == 403
    finally:
        asyncio.run(engine.dispose())
