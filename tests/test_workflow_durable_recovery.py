from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.core.state_machine as state_machine
from backend.core.state_machine import WorkflowRunner, WorkflowStep
from backend.database import Base
from backend.models import AuditLog, PausedSession, WorkflowRun, Workspace
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
    monkeypatch.setattr(state_machine, "SessionLocal", sessions)
    monkeypatch.setattr(
        state_machine,
        "get_settings",
        lambda: SimpleNamespace(
            execution_mode="SEMI_AUTONOMOUS",
            publishing_dry_run=True,
            load_yaml=lambda: {"app": {"workflow_step_timeout_seconds": 5, "max_workflow_retries": 0}},
        ),
    )
    async def no_emit(*args, **kwargs):
        return None
    monkeypatch.setattr(WorkflowRunner, "_emit", no_emit)
    async with sessions() as db:
        workspace = Workspace(name="Durable runner", slug=f"durable-{datetime.now().timestamp()}")
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        await db.commit()
    return engine, sessions, workspace_id


def _expired_lease():
    return datetime.now(timezone.utc) - timedelta(minutes=5)


@pytest.mark.asyncio
async def test_recovery_resumes_read_only_workflow_from_persisted_checkpoint(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    calls: list[str] = []
    try:
        with workspace_scope(workspace_id):
            async with sessions() as db:
                db.add(WorkflowRun(
                    id="workflow-recover-readonly",
                    workflow_name="recovery-test",
                    status="running",
                    current_step=1,
                    execution_mode="SEMI_AUTONOMOUS",
                    workspace_id=workspace_id,
                    state_json={"metadata": {"workspace_id": workspace_id}, "prior": "preserved"},
                    lease_owner="dead-worker",
                    lease_expires_at=_expired_lease(),
                    heartbeat_at=_expired_lease(),
                    attempt_count=1,
                ))
                await db.commit()

        async def stage0(state):
            calls.append("stage0")
            return {"stage0_result": {"status": "completed"}}

        async def stage1(state):
            calls.append("stage1")
            return {"stage1_result": {"status": "completed"}}

        async def stage2(state):
            calls.append("stage2")
            return {"stage2_result": {"status": "completed"}}

        runner = WorkflowRunner()
        runner.set_resolver(lambda name: [
            WorkflowStep("S1", "read one", stage0),
            WorkflowStep("S2", "read two", stage1),
            WorkflowStep("S3", "read three", stage2),
        ])
        assert await runner.recover_interrupted() == 1
        active = list(runner.tasks.values())
        assert len(active) == 1
        await asyncio.gather(*active)

        assert calls == ["stage1", "stage2"]
        with workspace_scope(workspace_id):
            async with sessions() as db:
                row = await db.get(WorkflowRun, "workflow-recover-readonly")
        assert row is not None
        assert row.status == "completed"
        assert row.attempt_count == 2
        assert row.lease_owner is None
        assert row.lease_expires_at is None
        assert row.state_json["prior"] == "preserved"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_live_side_effect_is_failed_for_manual_reconciliation_not_replayed(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    called = []
    try:
        with workspace_scope(workspace_id):
            async with sessions() as db:
                db.add(WorkflowRun(
                    id="workflow-recover-live-s5",
                    workflow_name="live-publish-test",
                    status="running",
                    current_step=0,
                    execution_mode="SEMI_AUTONOMOUS",
                    workspace_id=workspace_id,
                    state_json={
                        "metadata": {"workspace_id": workspace_id, "initiated_by": "operator@example.test"},
                        "publish_requests": [{"platform": "reddit", "post": {"title": "test"}}],
                    },
                    lease_owner="dead-worker",
                    lease_expires_at=_expired_lease(),
                    heartbeat_at=_expired_lease(),
                    attempt_count=1,
                ))
                await db.commit()

        async def live_publish(state):
            called.append(True)
            return {"s5_result": {"status": "published"}}

        runner = WorkflowRunner()
        runner.set_resolver(lambda name: [
            WorkflowStep("S5", "Distribution", live_publish, side_effecting=True),
        ])
        monkeypatch.setattr(
            state_machine,
            "get_settings",
            lambda: SimpleNamespace(
                execution_mode="SEMI_AUTONOMOUS",
                publishing_dry_run=False,
                load_yaml=lambda: {"app": {"workflow_step_timeout_seconds": 5, "max_workflow_retries": 0}},
            ),
        )
        assert await runner.recover_interrupted() == 1
        assert called == []
        assert runner.tasks == {}
        with workspace_scope(workspace_id):
            async with sessions() as db:
                row = await db.get(WorkflowRun, "workflow-recover-live-s5")
                audit = await db.scalar(select(AuditLog).where(
                    AuditLog.action == "workflow.side_effect_outcome_unknown",
                    AuditLog.resource_id == "workflow-recover-live-s5",
                ))
        assert row is not None and row.status == "failed"
        assert "must be reconciled" in (row.error_message or "")
        assert row.lease_owner is None
        assert audit is not None and audit.workspace_id == workspace_id
        assert audit.outcome == "unknown"
        assert audit.details_json["manual_reconciliation_required"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_active_workflow_lease_is_not_stolen(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    try:
        future = datetime.now(timezone.utc) + timedelta(minutes=3)
        with workspace_scope(workspace_id):
            async with sessions() as db:
                db.add(WorkflowRun(
                    id="workflow-active-lease",
                    workflow_name="active-test",
                    status="running",
                    current_step=0,
                    execution_mode="SEMI_AUTONOMOUS",
                    workspace_id=workspace_id,
                    state_json={"metadata": {"workspace_id": workspace_id}},
                    lease_owner="live-worker",
                    lease_expires_at=future,
                    heartbeat_at=datetime.now(timezone.utc),
                    attempt_count=1,
                ))
                await db.commit()

        runner = WorkflowRunner()
        runner.set_resolver(lambda name: [WorkflowStep("S1", "read", lambda state: _async_result())])
        assert await runner.recover_interrupted() == 0
        assert runner.tasks == {}
        with workspace_scope(workspace_id):
            async with sessions() as db:
                row = await db.get(WorkflowRun, "workflow-active-lease")
        assert row is not None
        assert row.lease_owner == "live-worker"
        assert row.attempt_count == 1
    finally:
        await engine.dispose()


async def _async_result():
    return {"result": {"status": "completed"}}


@pytest.mark.asyncio
async def test_expired_paused_session_is_recovered_and_can_resume(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    called: list[str] = []
    try:
        with workspace_scope(workspace_id):
            async with sessions() as db:
                db.add(WorkflowRun(
                    id="workflow-recover-paused",
                    workflow_name="paused-test",
                    status="paused",
                    current_step=0,
                    execution_mode="SEMI_AUTONOMOUS",
                    workspace_id=workspace_id,
                    state_json={"metadata": {"workspace_id": workspace_id}},
                    lease_owner="dead-worker",
                    lease_expires_at=_expired_lease(),
                    heartbeat_at=_expired_lease(),
                    attempt_count=1,
                ))
                db.add(PausedSession(
                    session_id="workflow-recover-paused",
                    workflow_name="paused-test",
                    status="paused",
                    current_step=0,
                    required_action="review",
                    state_json={"metadata": {"workspace_id": workspace_id}},
                    workspace_id=workspace_id,
                ))
                await db.commit()

        async def stage(state):
            called.append(str(state.get("_verification_response") or ""))
            return {"s1_result": {"status": "completed"}}

        runner = WorkflowRunner()
        runner.set_resolver(lambda name: [WorkflowStep("S1", "reviewed stage", stage)])
        assert await runner.recover_paused() == 1
        assert "workflow-recover-paused" in runner.tasks
        runner.responses["workflow-recover-paused"] = "approved"
        runner.events["workflow-recover-paused"].set()
        await asyncio.gather(runner.tasks["workflow-recover-paused"])

        assert called == ["approved"]
        with workspace_scope(workspace_id):
            async with sessions() as db:
                run = await db.get(WorkflowRun, "workflow-recover-paused")
                paused = await db.get(PausedSession, "workflow-recover-paused")
        assert run is not None and run.status == "completed"
        assert paused is not None and paused.status == "resuming"
    finally:
        await engine.dispose()
