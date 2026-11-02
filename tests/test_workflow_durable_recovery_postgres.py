from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.core.state_machine import WorkflowRunner, WorkflowStep
import backend.core.state_machine as state_machine
from backend.database import SessionLocal, engine
from backend.models import WorkflowRun, Workspace
from backend.tenancy import workspace_scope


@pytest.mark.asyncio
async def test_postgres_only_one_worker_claims_an_expired_workflow(monkeypatch):
    if not engine.url.drivername.startswith("postgresql"):
        pytest.skip("requires the dedicated PostgreSQL workflow-lease integration job")

    async def noop(state):
        return {"s1_result": {"status": "completed"}}

    workspace_id = None
    workflow_id = str(uuid.uuid4())
    try:
        async with SessionLocal() as db:
            workspace = Workspace(name="Workflow lease claim", slug=f"workflow-lease-{uuid.uuid4().hex}")
            db.add(workspace)
            await db.commit()
            workspace_id = workspace.id
        stale = datetime.now(timezone.utc) - timedelta(minutes=5)
        with workspace_scope(workspace_id):
            async with SessionLocal() as db:
                db.add(WorkflowRun(
                    id=workflow_id,
                    workflow_name="lease-claim-test",
                    status="queued",
                    current_step=0,
                    execution_mode="SEMI_AUTONOMOUS",
                    workspace_id=workspace_id,
                    state_json={"metadata": {"workspace_id": workspace_id}},
                    lease_owner="dead-worker",
                    lease_expires_at=stale,
                    heartbeat_at=stale,
                    attempt_count=1,
                ))
                await db.commit()

        first = WorkflowRunner()
        second = WorkflowRunner()
        resolver = lambda name: [WorkflowStep("S1", "read-only", noop)]
        first.set_resolver(resolver)
        second.set_resolver(resolver)
        claims = await asyncio.gather(first._claim_interrupted_row(), second._claim_interrupted_row())
        valid = [claim for claim in claims if claim is not None and not claim.get("reconciliation_only")]
        assert len(valid) == 1
        winner = valid[0]
        assert winner["session_id"] == workflow_id
        assert winner["worker_id"] in {first.worker_id, second.worker_id}

        async with SessionLocal() as db:
            row = await db.get(WorkflowRun, workflow_id)
        assert row is not None
        assert row.lease_owner == winner["worker_id"]
        assert row.attempt_count == 2
        assert row.lease_expires_at is not None and row.lease_expires_at > datetime.now(timezone.utc)
    finally:
        await engine.dispose()
