from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.core.state_machine import WorkflowRunner
import backend.core.state_machine as state_machine
from backend.database import Base
from backend.models import PausedSession, WorkflowRun, Workspace
from backend.tenancy import workspace_scope


def test_workflow_and_status_endpoints_require_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(status_code=401, detail="Authentication required")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    with TestClient(main.app) as client:
        responses = [
            client.post("/api/workflows/run", json={}),
            client.get("/api/workflows/not-a-real-session"),
            client.post("/api/resume/not-a-real-session", json={"verification_code": "test-code"}),
            client.get("/api/status"),
            client.get("/api/flywheel/status"),
        ]
    assert [response.status_code for response in responses] == [401] * len(responses)


@pytest.mark.asyncio
async def test_workflow_status_and_resume_are_bound_to_the_owner_workspace(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(state_machine, "SessionLocal", sessions)

        async with sessions() as db:
            workspace_a = Workspace(name="Workflow Workspace A", slug="workflow-tenant-a")
            workspace_b = Workspace(name="Workflow Workspace B", slug="workflow-tenant-b")
            db.add_all([workspace_a, workspace_b])
            await db.flush()
            workspace_a_id, workspace_b_id = workspace_a.id, workspace_b.id
            await db.commit()

        workflow_id = "b0eab776-2b54-4b04-9150-68ee2484d611"
        with workspace_scope(workspace_a_id):
            async with sessions() as db:
                db.add(WorkflowRun(
                    id=workflow_id,
                    workflow_name="full_flywheel",
                    status="paused",
                    execution_mode="SEMI_AUTONOMOUS",
                    state_json={"metadata": {"workspace_id": workspace_a_id}},
                    workspace_id=workspace_a_id,
                ))
                db.add(PausedSession(
                    session_id=workflow_id,
                    workflow_name="full_flywheel",
                    status="paused",
                    current_step=0,
                    required_action="verification",
                    state_json={"metadata": {"workspace_id": workspace_a_id}},
                    workspace_id=workspace_a_id,
                ))
                await db.commit()

        runner = WorkflowRunner()
        assert await runner.status(workflow_id, workspace_id=workspace_b_id) is None
        with pytest.raises(KeyError, match="Paused session not found"):
            await runner.resume(workflow_id, "not-a-real-verification", workspace_id=workspace_b_id)

        own = await runner.status(workflow_id, workspace_id=workspace_a_id)
        assert own is not None
        assert own["status"] == "paused"
        assert own["paused_session"]["status"] == "paused"

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_runner_rejects_unscoped_starts():
    runner = WorkflowRunner()
    with workspace_scope(None):
        with pytest.raises(ValueError, match="Authorized workspace context"):
            await runner.start("full_flywheel", {}, [], "SEMI_AUTONOMOUS")
