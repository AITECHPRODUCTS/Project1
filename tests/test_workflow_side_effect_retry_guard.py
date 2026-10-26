from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.core.state_machine as state_machine
from backend.core.state_machine import WorkflowRunner, WorkflowStep
from backend.database import Base
from backend.models import AuditLog, WorkflowRun, Workspace
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
    monkeypatch.setattr(state_machine, "get_settings", lambda: SimpleNamespace(
        load_yaml=lambda: {"app": {"workflow_step_timeout_seconds": 10, "max_workflow_retries": 2}}
    ))
    async def no_emit(*args, **kwargs):
        return None
    monkeypatch.setattr(WorkflowRunner, "_emit", no_emit)
    async with sessions() as db:
        workspace = Workspace(name="Retry guard workspace", slug="retry-guard")
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        db.add(WorkflowRun(
            id="workflow-retry-guard",
            workflow_name="test-workflow",
            status="queued",
            execution_mode="SEMI_AUTONOMOUS",
            workspace_id=workspace_id,
            state_json={"metadata": {"workspace_id": workspace_id}},
        ))
        await db.commit()
    return engine, sessions, workspace_id


@pytest.mark.asyncio
async def test_external_side_effect_transient_error_is_not_retried_and_is_audited(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    try:
        called = 0

        async def publish_with_ambiguous_transport_failure(state):
            nonlocal called
            called += 1
            raise ConnectionError("provider connection dropped after request")

        runner = WorkflowRunner()
        state = {"metadata": {"workspace_id": workspace_id, "initiated_by": "operator@example.test"}}
        with workspace_scope(workspace_id):
            await runner._drive(
                "workflow-retry-guard",
                "test-workflow",
                state,
                [WorkflowStep("S5", "Distribution", publish_with_ambiguous_transport_failure, side_effecting=True)],
                0,
                "SEMI_AUTONOMOUS",
            )

        assert called == 1
        async with sessions() as db:
            run = await db.get(WorkflowRun, "workflow-retry-guard")
            event = await db.scalar(select(AuditLog).where(
                AuditLog.action == "workflow.side_effect_outcome_unknown",
                AuditLog.resource_id == "workflow-retry-guard",
            ))
        assert run is not None and run.status == "failed"
        assert "automatic retry suppressed" in (run.error_message or "")
        assert event is not None
        assert event.workspace_id == workspace_id
        assert event.outcome == "unknown"
        assert event.details_json == {
            "stage": "S5",
            "error_type": "ConnectionError",
            "automatic_retry": False,
            "manual_reconciliation_required": True,
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_read_only_transient_error_keeps_configured_retry_behavior(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    try:
        calls = 0

        async def flaky_read(state):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("temporary read-only lookup failure")
            return {"s1_result": {"status": "completed", "value": "retrieved"}}

        runner = WorkflowRunner()
        state = {"metadata": {"workspace_id": workspace_id}}
        with workspace_scope(workspace_id):
            await runner._drive(
                "workflow-retry-guard",
                "test-workflow",
                state,
                [WorkflowStep("S1", "Research", flaky_read)],
                0,
                "SEMI_AUTONOMOUS",
            )

        assert calls == 3
        async with sessions() as db:
            run = await db.get(WorkflowRun, "workflow-retry-guard")
        assert run is not None and run.status == "completed"
    finally:
        await engine.dispose()
