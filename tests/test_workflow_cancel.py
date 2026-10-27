from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend import core
from backend.core import state_machine
from backend.core.state_machine import WorkflowRunner, WorkflowStep
from backend.models import AuditLog, PausedSession, WorkflowRun, Workspace


def _runner_db(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(state_machine, "SessionLocal", sessions)

    async def seed():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(Workspace(id="cancel-workspace-a", name="Cancel workspace A", slug="cancel-workspace-a"))
            db.add(Workspace(id="cancel-workspace-b", name="Cancel workspace B", slug="cancel-workspace-b"))
            await db.commit()

    asyncio.run(seed())
    return engine, sessions


async def _insert_run(sessions, *, sid="workflow-cancel-1", workspace_id="cancel-workspace-a", status="queued"):
    async with sessions() as db:
        db.add(WorkflowRun(
            id=sid,
            workspace_id=workspace_id,
            workflow_name="cancel-test",
            status=status,
            current_step=0,
            execution_mode="SEMI_AUTONOMOUS",
            state_json={"metadata":{"workspace_id":workspace_id,"initiated_by":"operator@example.invalid"}},
            result_json={},
        ))
        await db.commit()


@pytest.mark.asyncio
async def test_cancel_during_running_stage_finishes_that_stage_then_skips_later_stages(monkeypatch):
    engine, sessions = _runner_db(monkeypatch)
    runner = WorkflowRunner()
    started = asyncio.Event()
    release_stage = asyncio.Event()
    calls = []
    async def current_stage(state):
        started.set()
        await release_stage.wait()
        calls.append("current")
        return {"current_stage_result":{"accepted":True}}
    async def next_stage(state):
        calls.append("next")
        return {"next_stage_result":{"unexpected":True}}
    steps = [
        WorkflowStep("S1","Current stage",current_stage),
        WorkflowStep("S2","Next stage",next_stage),
    ]
    try:
        await _insert_run(sessions)
        state={"metadata":{"workspace_id":"cancel-workspace-a","initiated_by":"operator@example.invalid"}}
        task=asyncio.create_task(runner._drive("workflow-cancel-1","cancel-test",state,steps,0,"SEMI_AUTONOMOUS"))
        runner.tasks["workflow-cancel-1"]=task
        await asyncio.wait_for(started.wait(),timeout=2)
        requested=await runner.request_cancel("workflow-cancel-1","cancel-workspace-a",actor="operator@example.invalid")
        assert requested["status"]=="cancel_requested"
        assert requested["cancel_requested"] is True
        release_stage.set()
        await asyncio.wait_for(task,timeout=3)
        async with sessions() as db:
            row=await db.get(WorkflowRun,"workflow-cancel-1")
            audits=list((await db.scalars(select(AuditLog).where(
                AuditLog.workspace_id=="cancel-workspace-a",
                AuditLog.resource_id=="workflow-cancel-1",
                AuditLog.action.in_(["workflow.cancel_requested","workflow.cancelled"]),
            ))).all())
        assert row is not None and row.status=="cancelled"
        assert row.current_step==1
        assert row.state_json["stages"]["S1"]["result"]["current_stage_result"]["accepted"] is True
        assert row.state_json["control"]["cancel_requested"] is True
        assert calls==["current"]
        assert {item.action for item in audits}=={"workflow.cancel_requested","workflow.cancelled"}
    finally:
        task=runner.tasks.pop("workflow-cancel-1",None)
        if task is not None and not task.done():
            release_stage.set()
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_before_execution_is_durable_and_first_handler_never_runs(monkeypatch):
    engine, sessions = _runner_db(monkeypatch)
    runner=WorkflowRunner()
    called=[]
    async def should_not_run(state):
        called.append(True)
        return {"side_effect":{"sent":True}}
    try:
        await _insert_run(sessions)
        requested=await runner.request_cancel("workflow-cancel-1","cancel-workspace-a",actor="operator@example.invalid")
        assert requested["status"]=="cancel_requested"
        await runner._drive(
            "workflow-cancel-1","cancel-test",
            {"metadata":{"workspace_id":"cancel-workspace-a"}},
            [WorkflowStep("S1","Should not run",should_not_run)],0,"SEMI_AUTONOMOUS",
        )
        async with sessions() as db:
            row=await db.get(WorkflowRun,"workflow-cancel-1")
        assert row is not None and row.status=="cancelled"
        assert called==[]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_is_workspace_scoped_and_repeated_request_is_idempotent(monkeypatch):
    engine, sessions=_runner_db(monkeypatch)
    runner=WorkflowRunner()
    try:
        await _insert_run(sessions)
        with pytest.raises(KeyError):
            await runner.request_cancel("workflow-cancel-1","cancel-workspace-b",actor="other@example.invalid")
        first=await runner.request_cancel("workflow-cancel-1","cancel-workspace-a",actor="operator@example.invalid")
        second=await runner.request_cancel("workflow-cancel-1","cancel-workspace-a",actor="operator@example.invalid")
        assert first["duplicate"] is False
        assert second["duplicate"] is True
        with pytest.raises(ValueError,match="terminal workflow cannot be cancelled"):
            async with sessions() as db:
                row=await db.get(WorkflowRun,"workflow-cancel-1")
                row.status="completed"
                await db.commit()
            await runner.request_cancel("workflow-cancel-1","cancel-workspace-a",actor="operator@example.invalid")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancellation_while_paused_wakes_worker_and_clears_persisted_hitl_response(monkeypatch):
    from backend.core.errors import VerificationRequiredError

    engine, sessions=_runner_db(monkeypatch)
    runner=WorkflowRunner()
    started=asyncio.Event()
    calls=[]
    async def must_pause(state):
        calls.append("attempt")
        started.set()
        raise VerificationRequiredError("merchant approval required")
    async def never_run(state):
        calls.append("next")
        return {}
    steps=[WorkflowStep("S1","Approval",must_pause),WorkflowStep("S2","Next",never_run)]
    task=None
    try:
        await _insert_run(sessions)
        state={"metadata":{"workspace_id":"cancel-workspace-a"}}
        task=asyncio.create_task(runner._drive("workflow-cancel-1","cancel-test",state,steps,0,"SEMI_AUTONOMOUS"))
        runner.tasks["workflow-cancel-1"]=task
        await asyncio.wait_for(started.wait(),timeout=2)
        for _ in range(100):
            async with sessions() as db:
                row=await db.get(WorkflowRun,"workflow-cancel-1")
            if row and row.status=="paused":break
            await asyncio.sleep(.01)
        assert row is not None and row.status=="paused"
        with state_machine.workspace_scope("cancel-workspace-a"):
            async with sessions() as db:
                paused=await db.get(PausedSession,"workflow-cancel-1")
                paused.verification_response_encrypted="encrypted-placeholder"
                await db.commit()
        result=await runner.request_cancel("workflow-cancel-1","cancel-workspace-a",actor="operator@example.invalid")
        assert result["status"]=="cancel_requested"
        await asyncio.wait_for(task,timeout=3)
        async with sessions() as db:
            row=await db.get(WorkflowRun,"workflow-cancel-1")
            paused=await db.get(PausedSession,"workflow-cancel-1")
        assert row is not None and row.status=="cancelled"
        assert paused is not None and paused.status=="cancelled"
        assert paused.verification_response_encrypted is None
        assert calls==["attempt"]
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        await engine.dispose()
