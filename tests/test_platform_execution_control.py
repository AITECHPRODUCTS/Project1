from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, PlatformExecutionControl, Workspace
from backend.schemas import PlatformExecutionControlChangeRequest
from backend.services.external_action_registry import claim_external_action
from backend.tenancy import workspace_scope


ADMIN_WORKSPACE = "30000000-0000-4000-8000-000000000001"


async def _setup(monkeypatch, *, seed_control: bool = True):
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
        db.add(Workspace(
            id=ADMIN_WORKSPACE,
            name="Platform control audit workspace",
            slug="platform-control-audit-workspace",
        ))
        if seed_control:
            db.add(PlatformExecutionControl(id=1, outbound_actions_paused=False))
        await db.commit()
    return engine, sessions


def _set_user(monkeypatch, *, is_admin: bool = True):
    async def current_user():
        return {
            "email": "platform-control-operator@example.invalid",
            "user_id": "platform-control-operator",
            "workspace_id": ADMIN_WORKSPACE,
            "workspace_role": "owner",
            "is_admin": is_admin,
        }
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, current_user)


def test_platform_execution_control_requires_reason_and_records_pause_resume_audit(monkeypatch):
    async def run_test():
        engine, sessions = await _setup(monkeypatch)
        _set_user(monkeypatch)
        try:
            with TestClient(main.app) as client:
                before = client.get("/api/admin/execution-control")
                invalid = client.post("/api/admin/execution-control", json={
                    "outbound_actions_paused": True,
                    "reason": "   ",
                })
                paused = client.post("/api/admin/execution-control", json={
                    "outbound_actions_paused": True,
                    "reason": "Security incident investigation is underway",
                })
                after_pause = client.get("/api/admin/execution-control")
                resumed = client.post("/api/admin/execution-control", json={
                    "outbound_actions_paused": False,
                    "reason": "Incident was reviewed and provider writes can resume",
                })
            assert before.status_code == 200, before.text
            assert before.json()["outbound_actions_paused"] is False
            assert invalid.status_code == 422
            assert paused.status_code == 200, paused.text
            assert after_pause.json()["outbound_actions_paused"] is True
            assert after_pause.json()["reason"] == "Security incident investigation is underway"
            assert after_pause.json()["completed_idempotency_replays_allowed"] is True
            assert after_pause.json()["in_flight_actions_cancelled"] is False
            assert resumed.status_code == 200, resumed.text
            assert resumed.json()["outbound_actions_paused"] is False
            async with sessions() as db:
                control = await db.get(PlatformExecutionControl, 1)
                with workspace_scope(ADMIN_WORKSPACE):
                    audits = list((await db.scalars(select(AuditLog).where(
                        AuditLog.action.in_([
                            "platform.outbound_actions.paused",
                            "platform.outbound_actions.resumed",
                        ]),
                        AuditLog.resource_id == "1",
                    ).order_by(AuditLog.action.asc()))).all())
            assert control is not None and control.outbound_actions_paused is False
            assert len(audits) == 2
            by_action = {item.action: item for item in audits}
            assert by_action["platform.outbound_actions.paused"].details_json["reason"] == "Security incident investigation is underway"
            assert by_action["platform.outbound_actions.paused"].details_json["new_paused"] is True
            assert by_action["platform.outbound_actions.resumed"].details_json["new_paused"] is False
            assert all(item.workspace_id == ADMIN_WORKSPACE for item in audits)
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)


def test_non_platform_admin_cannot_read_or_change_global_execution_control(monkeypatch):
    async def run_test():
        engine, _ = await _setup(monkeypatch)
        _set_user(monkeypatch, is_admin=False)
        try:
            with TestClient(main.app) as client:
                read = client.get("/api/admin/execution-control")
                write = client.post("/api/admin/execution-control", json={
                    "outbound_actions_paused": True,
                    "reason": "Security incident investigation is underway",
                })
            assert read.status_code == 403
            assert write.status_code == 403
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)


def test_global_execution_control_row_missing_fails_closed_for_provider_claim(monkeypatch):
    async def run_test():
        engine, sessions = await _setup(monkeypatch, seed_control=False)
        try:
            async with sessions() as db:
                with workspace_scope(ADMIN_WORKSPACE):
                    with pytest.raises(HTTPException) as error:
                        await claim_external_action(
                            db,
                            workspace_id=ADMIN_WORKSPACE,
                            action_type="social_publish",
                            provider="reddit",
                            idempotency_key="missing-global-control-01",
                            request_payload={"post": {"text": "Reviewed"}},
                        )
                assert error.value.status_code == 503
                assert error.value.detail["code"] == "PLATFORM_EXECUTION_CONTROL_UNAVAILABLE"
                assert await db.get(PlatformExecutionControl, 1) is None
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)


def test_execution_control_request_rejects_blank_short_and_extra_fields():
    valid = PlatformExecutionControlChangeRequest(
        outbound_actions_paused=True,
        reason="Confirmed provider incident response",
    )
    assert valid.outbound_actions_paused is True
    assert valid.reason == "Confirmed provider incident response"
    with pytest.raises(ValidationError):
        PlatformExecutionControlChangeRequest(outbound_actions_paused=True, reason="short")
    with pytest.raises(ValidationError):
        PlatformExecutionControlChangeRequest(
            outbound_actions_paused=True,
            reason="Confirmed provider incident response",
            force=True,
        )
