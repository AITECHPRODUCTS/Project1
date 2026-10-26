from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main, workflows
from backend.database import Base
from backend.models import AuditLog, Conversion, Workspace
from backend.tenancy import workspace_scope


def _user(*, platform_admin: bool, workspace_id: str | None = "workflow-publish-ws"):
    async def current_user():
        return {
            "email": "operator@example.invalid",
            "user_id": "operator-1",
            "workspace_id": workspace_id,
            "workspace_role": "owner" if platform_admin else "member",
            "is_admin": platform_admin,
        }
    return current_user


def _publish_state(**metadata):
    return {
        "publish_requests": [{"platform": "reddit", "post": {"subreddit": "test", "title": "Reviewed draft", "text": "Draft text"}}],
        "metadata": metadata,
    }


def test_workflow_live_publish_requires_platform_admin_and_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(main.settings, "publishing_dry_run", False)
    calls = []

    async def fake_start(name, state, steps, mode=None):
        calls.append((name, state, mode))
        return "workflow-test-id"

    monkeypatch.setattr(main.runner, "start", fake_start)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, _user(platform_admin=False))
    with TestClient(main.app) as client:
        denied_role = client.post("/api/workflows/run", json={
            "workflow_name": "S5",
            "state": _publish_state(platform_admin_authorized=True, live_publish_confirmed=True),
            "confirm_live_publish": True,
        })
    assert denied_role.status_code == 403
    assert calls == []

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, _user(platform_admin=True))
    with TestClient(main.app) as client:
        denied_confirmation = client.post("/api/workflows/run", json={
            "workflow_name": "S5",
            "state": _publish_state(platform_admin_authorized=True, live_publish_confirmed=True),
        })
    assert denied_confirmation.status_code == 409
    assert calls == []

    with TestClient(main.app) as client:
        approved = client.post("/api/workflows/run", json={
            "workflow_name": "S5",
            "state": _publish_state(platform_admin_authorized=False, live_publish_confirmed=False),
            "confirm_live_publish": True,
        })
    assert approved.status_code == 202, approved.text
    assert len(calls) == 1
    trusted_metadata = calls[0][1]["metadata"]
    assert trusted_metadata["platform_admin_authorized"] is True
    assert trusted_metadata["live_publish_confirmed"] is True
    assert trusted_metadata["initiated_by"] == "operator@example.invalid"
    assert trusted_metadata["workspace_id"] == "workflow-publish-ws"


@pytest.mark.asyncio
async def test_workflow_distribution_stage_denies_spoofed_live_authorization(monkeypatch):
    monkeypatch.setattr(workflows, "get_settings", lambda: SimpleNamespace(publishing_dry_run=False))
    calls = []

    async def fake_publish(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "published"}

    monkeypatch.setattr(workflows, "social_media_scheduler", fake_publish)
    state = _publish_state(
        workspace_id="spoofed-workspace",
        platform_admin_authorized=False,
        live_publish_confirmed=False,
    )
    # The stage itself independently fails closed when trusted authorization is absent.
    with pytest.raises(PermissionError, match="Platform Super Admin"):
        await workflows.s5(state)
    assert calls == []


@pytest.mark.asyncio
async def test_workflow_distribution_audits_tenant_bound_attempt_and_outcome(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(workflows, "SessionLocal", sessions)
        monkeypatch.setattr(workflows, "get_settings", lambda: SimpleNamespace(publishing_dry_run=True))
        workspace_id = "workflow-publish-workspace"
        async with sessions() as db:
            db.add(Workspace(id=workspace_id, name="Workflow publish", slug="workflow-publish"))
            await db.commit()

        async def fake_publish(platform, post):
            return {"status": "dry_run", "platform": platform, "remote_id": None}

        monkeypatch.setattr(workflows, "social_media_scheduler", fake_publish)
        state = _publish_state(
            workspace_id=workspace_id,
            workflow="S5",
            execution_mode="SEMI_AUTONOMOUS",
            initiated_by="operator@example.invalid",
            platform_admin_authorized=False,
            live_publish_confirmed=False,
        )
        with workspace_scope(workspace_id):
            result = await workflows.s5(state)
        assert result["s5_result"]["publish_results"][0]["status"] == "dry_run"
        async with sessions() as db:
            events = list((await db.scalars(select(AuditLog).where(AuditLog.action == "workflow.social_publish"))).all())
        assert len(events) == 2
        assert {event.workspace_id for event in events} == {workspace_id}
        assert {event.outcome for event in events} == {"requested", "dry_run"}
        assert all(event.details_json["platform"] == "reddit" for event in events)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_conversion_import_deduplication_is_per_workspace(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(workflows, "SessionLocal", sessions)
        async with sessions() as db:
            workspace_a = Workspace(name="Conversion workflow A", slug="workflow-conv-a")
            workspace_b = Workspace(name="Conversion workflow B", slug="workflow-conv-b")
            db.add_all([workspace_a, workspace_b])
            await db.flush()
            workspace_a_id, workspace_b_id = workspace_a.id, workspace_b.id
            await db.commit()

        event = {"network": "example-network", "external_event_id": "same-event-1", "commission": 1.5, "revenue": 10.0}
        with workspace_scope(workspace_a_id):
            result_a = await workflows.s6({"metadata": {"workspace_id": workspace_a_id}, "conversion_events": [event]})
        with workspace_scope(workspace_b_id):
            result_b = await workflows.s6({"metadata": {"workspace_id": workspace_b_id}, "conversion_events": [event]})
        with workspace_scope(workspace_a_id):
            duplicate_a = await workflows.s6({"metadata": {"workspace_id": workspace_a_id}, "conversion_events": [event]})

        assert result_a["s6_result"]["conversion_events_saved"] == 1
        assert result_b["s6_result"]["conversion_events_saved"] == 1
        assert duplicate_a["s6_result"]["conversion_events_saved"] == 0
        async with sessions() as db:
            rows = list((await db.scalars(select(Conversion).where(
                Conversion.network == "example-network",
                Conversion.external_event_id == "same-event-1",
            ))).all())
        assert {(row.workspace_id, row.external_event_id) for row in rows} == {
            (workspace_a_id, "same-event-1"),
            (workspace_b_id, "same-event-1"),
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_conversion_import_rejects_missing_workspace():
    with pytest.raises(ValueError, match="Authorized workspace context required"):
        await workflows.s6({"conversion_events": [{"network": "example-network", "external_event_id": "event-1"}]})
