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
            app_session_secret="stable-test-session-secret-for-hitl-encryption",
            execution_mode="SEMI_AUTONOMOUS",
            publishing_dry_run=True,
            load_yaml=lambda: {"app": {"workflow_step_timeout_seconds": 5, "max_workflow_retries": 0}},
        ),
    )

    async def no_emit(*args, **kwargs):
        return None

    monkeypatch.setattr(WorkflowRunner, "_emit", no_emit)
    async with sessions() as db:
        workspace = Workspace(name="Persisted HITL", slug=f"hitl-{datetime.now().timestamp()}")
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        await db.commit()
    return engine, sessions, workspace_id


async def _add_paused(sessions, workspace_id, sid, lease_owner, lease_expires_at):
    with workspace_scope(workspace_id):
        async with sessions() as db:
            db.add(WorkflowRun(
                id=sid,
                workflow_name="hitl-persist-test",
                status="paused",
                current_step=0,
                execution_mode="SEMI_AUTONOMOUS",
                workspace_id=workspace_id,
                state_json={"metadata": {"workspace_id": workspace_id}},
                lease_owner=lease_owner,
                lease_expires_at=lease_expires_at,
                heartbeat_at=datetime.now(timezone.utc),
                attempt_count=1,
            ))
            db.add(PausedSession(
                session_id=sid,
                workflow_name="hitl-persist-test",
                status="paused",
                current_step=0,
                required_action="provider_verification",
                state_json={"metadata": {"workspace_id": workspace_id}},
                workspace_id=workspace_id,
            ))
            await db.commit()


@pytest.mark.asyncio
async def test_response_submitted_to_other_instance_is_encrypted_and_wakes_lease_owner(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    sid = "workflow-hitl-cross-worker"
    received: list[str] = []
    try:
        owner = WorkflowRunner()

        async def stage(state):
            received.append(str(state.get("_verification_response") or ""))
            return {"s1_result": {"status": "completed"}}

        step = WorkflowStep("S1", "Human verification", stage)
        owner.set_resolver(lambda _name: [step])
        await _add_paused(
            sessions, workspace_id, sid, owner.worker_id,
            datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        owner.events[sid] = asyncio.Event()
        operation = owner._wait_recovered_pause(
            sid, "hitl-persist-test",
            {"metadata": {"workspace_id": workspace_id}},
            [step], 0, "SEMI_AUTONOMOUS", "provider_verification", None,
            worker_id=owner.worker_id,
        )
        task = asyncio.create_task(owner._with_heartbeat(sid, owner.worker_id, workspace_id, operation))
        owner.tasks[sid] = task
        await asyncio.sleep(0.03)

        requester = WorkflowRunner()
        result = await requester.resume(
            sid, "one-time-code-482913", workspace_id=workspace_id,
            actor="operator@example.invalid",
        )
        assert result["status"] == "resume_requested"
        assert result["verification_response_persisted"] is True
        assert result["duplicate"] is False

        with workspace_scope(workspace_id):
            async with sessions() as db:
                paused = await db.get(PausedSession, sid)
                audit = await db.scalar(select(AuditLog).where(
                    AuditLog.action == "workflow.resume_requested",
                    AuditLog.resource_id == sid,
                ))
        assert paused is not None
        assert paused.verification_response_encrypted is not None
        assert "one-time-code-482913" not in paused.verification_response_encrypted
        assert state_machine._decrypt_resume_response(paused.verification_response_encrypted) == "one-time-code-482913"
        assert audit is not None and audit.workspace_id == workspace_id
        assert audit.details_json == {"verification_response_persisted": True, "encrypted_at_rest": True}
        assert await owner.wake_pending_responses() == 1

        await asyncio.wait_for(task, timeout=5)
        assert received == ["one-time-code-482913"]
        with workspace_scope(workspace_id):
            async with sessions() as db:
                paused = await db.get(PausedSession, sid)
                run = await db.get(WorkflowRun, sid)
        assert paused is not None and paused.verification_response_encrypted is None
        assert run is not None and run.status == "completed"
        assert run.state_json.get("_verification_response") is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resume_payload_survives_process_restart_and_is_consumed_before_waiting(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    sid = "workflow-hitl-restart"
    received: list[str] = []
    try:
        await _add_paused(
            sessions, workspace_id, sid, "crashed-worker",
            datetime.now(timezone.utc) - timedelta(minutes=4),
        )
        requester = WorkflowRunner()
        result = await requester.resume(
            sid, "approved-after-restart", workspace_id=workspace_id,
            actor="operator@example.invalid",
        )
        assert result["verification_response_persisted"] is True

        recovered = WorkflowRunner()

        async def stage(state):
            received.append(str(state.get("_verification_response") or ""))
            return {"s1_result": {"status": "completed"}}

        recovered.set_resolver(lambda _name: [WorkflowStep("S1", "Resume stage", stage)])
        assert await recovered.recover_paused() == 1
        task = recovered.tasks[sid]
        await asyncio.wait_for(task, timeout=5)

        assert received == ["approved-after-restart"]
        with workspace_scope(workspace_id):
            async with sessions() as db:
                paused = await db.get(PausedSession, sid)
                run = await db.get(WorkflowRun, sid)
        assert paused is not None and paused.status == "resuming"
        assert paused.verification_response_encrypted is None
        assert run is not None and run.status == "completed"
    finally:
        await engine.dispose()
