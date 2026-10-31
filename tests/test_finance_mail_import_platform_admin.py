from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, Workspace
import backend.services.commission_mail_importer as importer


def _override_user(monkeypatch, *, platform_admin: bool, workspace_id: str | None):
    async def current_user():
        return {
            "email": "mail-import-operator@example.invalid",
            "user_id": "mail-import-operator",
            "workspace_id": workspace_id,
            "workspace_role": "owner" if platform_admin else "admin",
            "is_admin": platform_admin,
        }
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, current_user)


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
        async with sessions() as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    workspace_id = "mail-import-audit-workspace"
    async with sessions() as db:
        db.add(Workspace(id=workspace_id, name="Mail import audit", slug="mail-import-audit"))
        await db.commit()
    return engine, sessions, workspace_id


def test_workspace_admin_cannot_trigger_global_mailbox_import(monkeypatch):
    _override_user(monkeypatch, platform_admin=False, workspace_id="workspace-admin-tenant")
    calls = []

    async def fake_import(**kwargs):
        calls.append(kwargs)
        return {"messages_matched": 1, "rows_created": 1}

    monkeypatch.setattr(importer, "import_commission_emails", fake_import)
    with TestClient(main.app) as client:
        response = client.post("/api/finance/email-import")
    assert response.status_code == 403
    assert "Platform Super Admin" in response.text
    assert calls == []


def test_platform_admin_without_workspace_cannot_trigger_global_mailbox_import(monkeypatch):
    _override_user(monkeypatch, platform_admin=True, workspace_id=None)
    calls = []

    async def fake_import(**kwargs):
        calls.append(kwargs)
        return {"messages_matched": 1, "rows_created": 1}

    monkeypatch.setattr(importer, "import_commission_emails", fake_import)
    with TestClient(main.app) as client:
        response = client.post("/api/finance/email-import")
    assert response.status_code == 403
    assert calls == []


@pytest.mark.asyncio
async def test_platform_admin_mail_import_is_audited_without_storing_mail_body(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)
        calls = []

        async def fake_import(**kwargs):
            calls.append(kwargs)
            return {
                "messages_matched": 3,
                "rows_created": 2,
                "note": "Parsed observations remain pending verification.",
            }

        monkeypatch.setattr(importer, "import_commission_emails", fake_import)
        with TestClient(main.app) as client:
            response = client.post("/api/finance/email-import")

        assert response.status_code == 200, response.text
        assert response.json()["rows_created"] == 2
        assert calls == [{"workspace_id": workspace_id}]
        async with sessions() as db:
            audit = await db.scalar(select(AuditLog).where(AuditLog.action == "finance.email_import"))
        assert audit is not None
        assert audit.workspace_id == workspace_id
        assert audit.actor == "mail-import-operator@example.invalid"
        assert audit.outcome == "completed"
        assert audit.details_json == {
            "provider": "imap",
            "mailbox": "INBOX",
            "messages_matched": 3,
            "rows_created": 2,
        }
        assert "body" not in str(audit.details_json).lower()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mail_import_failure_is_audited_and_returns_502(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    try:
        _override_user(monkeypatch, platform_admin=True, workspace_id=workspace_id)

        async def fail_import(**kwargs):
            raise TimeoutError("shared mailbox unavailable")

        monkeypatch.setattr(importer, "import_commission_emails", fail_import)
        with TestClient(main.app) as client:
            response = client.post("/api/finance/email-import")

        assert response.status_code == 502
        async with sessions() as db:
            audit = await db.scalar(select(AuditLog).where(AuditLog.action == "finance.email_import"))
        assert audit is not None
        assert audit.workspace_id == workspace_id
        assert audit.outcome == "failed"
        assert audit.details_json["error_type"] == "TimeoutError"
        assert "shared mailbox unavailable" not in str(audit.details_json)
    finally:
        await engine.dispose()
