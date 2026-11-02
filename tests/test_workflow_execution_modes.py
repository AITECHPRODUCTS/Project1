from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.core.state_machine as state_machine
from backend.core.errors import VerificationRequiredError
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
            execution_mode="FULL_AUTONOMOUS",
            publishing_dry_run=True,
            load_yaml=lambda: {
                "app": {
                    "workflow_step_timeout_seconds": 5,
                    "max_workflow_retries": 0,
                }
            },
        ),
    )

    async def no_emit(*args, **kwargs):
        return None

    monkeypatch.setattr(WorkflowRunner, "_emit", no_emit)

    async with sessions() as db:
        workspace = Workspace(
            name="Execution mode workspace",
            slug=f"execution-mode-{datetime.now(timezone.utc).timestamp()}",
        )
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        db.add(
            WorkflowRun(
                id="workflow-full-auto-verification-gate",
                workflow_name="full_flywheel",
                status="queued",
                current_step=0,
                execution_mode="FULL_AUTONOMOUS",
                workspace_id=workspace_id,
                state_json={"metadata": {"workspace_id": workspace_id}},
            )
        )
        await db.commit()

    return engine, sessions, workspace_id


@pytest.mark.asyncio
async def test_full_autonomous_fails_closed_and_audits_required_human_verification(monkeypatch):
    engine, sessions, workspace_id = await _database(monkeypatch)
    stage_calls = []

    async def protected_stage(state):
        stage_calls.append("S5")
        raise VerificationRequiredError(
            "A human must verify the provider action before proceeding.",
            action="provider_verification",
        )

    async def later_stage(state):
        stage_calls.append("S6")
        return {"s6_result": {"status": "completed"}}

    runner = WorkflowRunner()
    steps = [
        WorkflowStep("S5", "Protected external action", protected_stage, side_effecting=True),
        WorkflowStep("S6", "Later stage", later_stage),
    ]
    state = {
        "metadata": {
            "workspace_id": workspace_id,
            "initiated_by": "operator@example.test",
        }
    }

    try:
        with workspace_scope(workspace_id):
            await runner._drive(
                "workflow-full-auto-verification-gate",
                "full_flywheel",
                state,
                steps,
                0,
                "FULL_AUTONOMOUS",
            )

            async with sessions() as db:
                run = await db.get(WorkflowRun, "workflow-full-auto-verification-gate")
                audit = await db.scalar(
                    select(AuditLog).where(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.action == "workflow.full_autonomous_blocked_for_verification",
                        AuditLog.resource_id == "workflow-full-auto-verification-gate",
                    )
                )
                paused = await db.scalar(
                    select(PausedSession).where(
                        PausedSession.workspace_id == workspace_id,
                        PausedSession.session_id == "workflow-full-auto-verification-gate",
                    )
                )

        assert stage_calls == ["S5"]
        assert run is not None
        assert run.status == "failed"
        assert run.current_step == 0
        assert "Human verification required in FULL_AUTONOMOUS mode" in (run.error_message or "")
        assert audit is not None
        assert audit.outcome == "blocked"
        assert audit.details_json == {
            "stage": "S5",
            "required_action": "provider_verification",
            "execution_mode": "FULL_AUTONOMOUS",
        }
        assert paused is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_manual_override_rejects_more_than_one_stage_before_start():
    runner = WorkflowRunner()

    async def noop(state):
        return {"result": "ok"}

    with workspace_scope(None):
        with pytest.raises(ValueError, match="MANUAL_OVERRIDE runs exactly one stage"):
            await runner.start(
                "manual_stage",
                {},
                [
                    WorkflowStep("S1", "First stage", noop),
                    WorkflowStep("S2", "Second stage", noop),
                ],
                mode="MANUAL_OVERRIDE",
            )
