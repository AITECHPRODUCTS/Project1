from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.core.state_machine as state_machine
from backend.core.state_machine import WorkflowRunner, WorkflowStep
from backend.database import Base
from backend.models import AuditLog, WorkflowRun, Workspace
from backend.tenancy import workspace_scope


WORKSPACE_ID = "20000000-0000-4000-8000-000000000001"


async def _db(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(state_machine, "SessionLocal", sessions)
    async with sessions() as db:
        db.add(Workspace(
            id=WORKSPACE_ID,
            name="Lifecycle workflow workspace",
            slug="lifecycle-workflow-workspace",
        ))
        await db.commit()
    return engine, sessions


@pytest.mark.asyncio
async def test_workflow_start_is_rejected_when_workspace_is_suspended(monkeypatch):
    engine, sessions = await _db(monkeypatch)
    try:
        async with sessions() as db:
            workspace = await db.get(Workspace, WORKSPACE_ID)
            assert workspace is not None
            workspace.lifecycle_state = "suspended"
            await db.commit()

        runner = WorkflowRunner()
        with workspace_scope(WORKSPACE_ID):
            with pytest.raises(ValueError, match="suspended or unavailable"):
                await runner.start("suspended-start-test", {}, [], "SEMI_AUTONOMOUS")
        async with sessions() as db:
            rows = list((await db.scalars(select(WorkflowRun))).all())
        assert rows == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_running_workflow_stops_before_next_stage_if_workspace_is_suspended(monkeypatch):
    engine, sessions = await _db(monkeypatch)
    runner = WorkflowRunner()
    calls: list[str] = []

    async def suspend_after_first_stage(state):
        calls.append("first")
        async with sessions() as db:
            workspace = await db.get(Workspace, WORKSPACE_ID)
            assert workspace is not None
            workspace.lifecycle_state = "suspended"
            await db.commit()
        return {"first_stage_result": {"completed": True}}

    async def must_not_start(state):
        calls.append("second")
        return {"second_stage_result": {"started": True}}

    task = None
    try:
        async with sessions() as db:
            db.add(WorkflowRun(
                id="lifecycle-workflow-run",
                workspace_id=WORKSPACE_ID,
                workflow_name="lifecycle-test",
                status="queued",
                execution_mode="SEMI_AUTONOMOUS",
                state_json={"metadata": {"workspace_id": WORKSPACE_ID}},
                result_json={},
            ))
            await db.commit()

        with workspace_scope(WORKSPACE_ID):
            task = asyncio.create_task(runner._drive(
                "lifecycle-workflow-run",
                "lifecycle-test",
                {"metadata": {"workspace_id": WORKSPACE_ID}},
                [
                    WorkflowStep("S1", "Current stage", suspend_after_first_stage),
                    WorkflowStep("S2", "Must not run", must_not_start),
                ],
                0,
                "SEMI_AUTONOMOUS",
            ))
        await asyncio.wait_for(task, timeout=5)

        async with sessions() as db:
            row = await db.get(WorkflowRun, "lifecycle-workflow-run")
            audits = list((await db.scalars(select(AuditLog).where(
                AuditLog.workspace_id == WORKSPACE_ID,
                AuditLog.resource_id == "lifecycle-workflow-run",
                AuditLog.action == "workflow.cancelled",
            ))).all())
        assert calls == ["first"]
        assert row is not None and row.status == "cancelled"
        assert row.state_json["control"]["cancel_reason"] == "workspace_suspended"
        assert audits and audits[0].details_json["reason"] == "workspace_suspended"
    finally:
        task = runner.tasks.pop("lifecycle-workflow-run", None)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()
