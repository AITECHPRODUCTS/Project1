from __future__ import annotations

import anyio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, PlatformIncident, WorkflowRun, Workspace
from backend.tenancy import workspace_scope


ADMIN_EMAIL = "platform-operator@example.test"


def _platform_admin(workspace_id: str) -> dict:
    return {
        "user_id": "platform-operator",
        "email": ADMIN_EMAIL,
        "is_admin": True,
        "account_type": "platform_admin",
        "workspace_id": workspace_id,
        "workspace_role": "owner",
    }


async def _seed_database(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with sessions() as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_get_session)
    admin_workspace_id = ""
    customer_workspace_id = ""
    async with sessions() as db:
        admin_workspace = Workspace(name="Operations admin", slug="ops-admin-workspace")
        customer_workspace = Workspace(name="Operations customer", slug="ops-customer-workspace")
        db.add_all([admin_workspace, customer_workspace])
        await db.flush()
        admin_workspace_id = admin_workspace.id
        customer_workspace_id = customer_workspace.id

        db.add_all([
            WorkflowRun(
                id="workflow-readonly-failed",
                workspace_id=customer_workspace_id,
                workflow_name="S1",
                status="failed",
                current_step=0,
                execution_mode="SEMI_AUTONOMOUS",
                attempt_count=1,
                state_json={
                    "metadata": {"workspace_id": customer_workspace_id},
                    "stages": {"S1": {"status": "failed", "error": "S1: ValueError: read-only research failed"}},
                },
                error_message="S1: ValueError: read-only research failed",
            ),
            WorkflowRun(
                id="workflow-publish-unknown",
                workspace_id=customer_workspace_id,
                workflow_name="S5",
                status="failed",
                current_step=0,
                execution_mode="SEMI_AUTONOMOUS",
                attempt_count=1,
                state_json={
                    "metadata": {"workspace_id": customer_workspace_id},
                    "stages": {"S5": {"status": "failed", "error": "S5: ConnectionError: remote result unknown"}},
                },
                error_message="S5: external side-effect outcome unknown; automatic retry suppressed",
            ),
        ])
        db.add(AuditLog(
            workspace_id=customer_workspace_id,
            actor="workflow",
            action="workflow.side_effect_outcome_unknown",
            resource_type="external_publication",
            resource_id="workflow-publish-unknown",
            outcome="unknown",
            details_json={
                "stage": "S5",
                "automatic_retry": False,
                "manual_reconciliation_required": True,
            },
        ))
        await db.commit()

    return engine, sessions, admin_workspace_id, customer_workspace_id


def _client(monkeypatch, user: dict):
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, lambda: user)
    return TestClient(main.app)


def test_platform_operations_are_global_bounded_and_restrict_retry_to_read_only_stages(monkeypatch):
    async def run_test():
        engine, sessions, admin_workspace_id, customer_workspace_id = await _seed_database(monkeypatch)
        try:
            client = _client(monkeypatch, _platform_admin(admin_workspace_id))
            retry_start = AsyncMock(return_value="workflow-readonly-retry-child")
            monkeypatch.setattr(main.runner, "start", retry_start)
            try:
                operations = client.get("/api/admin/operations?limit=50")
                assert operations.status_code == 200, operations.text
                body = operations.json()
                assert body["bounded_snapshot"] is True
                assert body["summary"]["failed_workflows"] == 2
                assert body["summary"]["workflow_reconciliation_required"] == 1
                by_id = {row["id"]: row for row in body["workflows"]}
                assert by_id["workflow-readonly-failed"]["workspace_id"] == customer_workspace_id
                assert by_id["workflow-readonly-failed"]["retry_eligible"] is True
                assert by_id["workflow-publish-unknown"]["manual_reconciliation_required"] is True
                assert by_id["workflow-publish-unknown"]["dead_letter_candidate"] is True
                assert by_id["workflow-publish-unknown"]["retry_eligible"] is False
                assert body["queue_dispatch_capability"] == "review_only_no_provider_dispatch_worker"
                assert body["distribution_queue"] == []

                retry = client.post(
                    "/api/admin/workflows/workflow-readonly-failed/retry-read-only",
                    json={"reason": "Retry failed read-only research stage", "confirm_retry": True},
                )
                assert retry.status_code == 202, retry.text
                assert retry.json()["retry_workflow_id"] == "workflow-readonly-retry-child"
                assert retry.json()["stage"] == "S1"
                assert retry.json()["external_side_effect_retry"] is False
                retry_start.assert_awaited_once()
                assert retry_start.await_args.args[0] == "S1"
                assert len(retry_start.await_args.args[2]) == 1
                assert retry_start.await_args.kwargs["mode"] == "MANUAL_OVERRIDE"
                retry_state = retry_start.await_args.args[1]
                assert retry_state["metadata"]["operator_retry_of"] == "workflow-readonly-failed"
                assert retry_state["metadata"]["operator_retry_reason"] == "Retry failed read-only research stage"

                duplicate = client.post(
                    "/api/admin/workflows/workflow-readonly-failed/retry-read-only",
                    json={"reason": "Retry this read-only stage again", "confirm_retry": True},
                )
                assert duplicate.status_code == 409
                retry_start.assert_awaited_once()

                unsafe = client.post(
                    "/api/admin/workflows/workflow-publish-unknown/retry-read-only",
                    json={"reason": "Do not replay uncertain provider calls", "confirm_retry": True},
                )
                assert unsafe.status_code == 409
                retry_start.assert_awaited_once()

                async with sessions() as db:
                    claim = await db.scalar(select(AuditLog).where(
                        AuditLog.action == "workflow.operator_retry_claimed",
                        AuditLog.resource_id == "workflow-readonly-failed",
                    ))
                    assert claim is not None
                    assert claim.workspace_id == admin_workspace_id
                    assert claim.details_json["external_side_effect_retry"] is False
            finally:
                client.close()
        finally:
            monkeypatch.delitem(main.app.dependency_overrides, main.require_auth, raising=False)
            monkeypatch.delitem(main.app.dependency_overrides, get_session, raising=False)
            await engine.dispose()

    anyio.run(run_test)


def test_platform_incident_lifecycle_is_persisted_idempotent_and_audited(monkeypatch):
    async def run_test():
        engine, sessions, admin_workspace_id, customer_workspace_id = await _seed_database(monkeypatch)
        try:
            client = _client(monkeypatch, _platform_admin(admin_workspace_id))
            try:
                created = client.post("/api/admin/incidents/from-workflow/workflow-publish-unknown")
                assert created.status_code == 201, created.text
                incident = created.json()
                assert incident["severity"] == "critical"
                assert incident["status"] == "open"
                assert incident["source_workspace_id"] == customer_workspace_id
                assert "remote result unknown" not in incident["summary"]

                repeated = client.post("/api/admin/incidents/from-workflow/workflow-publish-unknown")
                assert repeated.status_code == 200, repeated.text
                assert repeated.json()["id"] == incident["id"]
                assert repeated.json()["already_exists"] is True

                acknowledged = client.post(f"/api/admin/incidents/{incident['id']}/acknowledge")
                assert acknowledged.status_code == 200, acknowledged.text
                assert acknowledged.json()["status"] == "acknowledged"
                assert acknowledged.json()["acknowledged_by"] == ADMIN_EMAIL

                resolved = client.post(
                    f"/api/admin/incidents/{incident['id']}/resolve",
                    json={"reason": "Provider state manually reconciled and recorded"},
                )
                assert resolved.status_code == 200, resolved.text
                assert resolved.json()["status"] == "resolved"
                assert resolved.json()["resolution_note"] == "Provider state manually reconciled and recorded"

                async with sessions() as db:
                    stored = await db.get(PlatformIncident, incident["id"])
                    assert stored is not None and stored.status == "resolved"
                    actions = set((await db.scalars(select(AuditLog.action).where(
                        AuditLog.resource_type == "platform_incident",
                        AuditLog.resource_id == incident["id"],
                    ))).all())
                    assert actions == {
                        "platform.incident.created",
                        "platform.incident.acknowledged",
                        "platform.incident.resolved",
                    }
            finally:
                client.close()
        finally:
            monkeypatch.delitem(main.app.dependency_overrides, main.require_auth, raising=False)
            monkeypatch.delitem(main.app.dependency_overrides, get_session, raising=False)
            await engine.dispose()

    anyio.run(run_test)


def test_workspace_admin_cannot_access_platform_operations_even_with_global_admin_flag(monkeypatch):
    async def run_test():
        engine, sessions, admin_workspace_id, _ = await _seed_database(monkeypatch)
        try:
            user = _platform_admin(admin_workspace_id)
            user["account_type"] = "merchant_product_owner"
            client = _client(monkeypatch, user)
            try:
                response = client.get("/api/admin/operations")
                assert response.status_code == 403
                assert "Platform Super Admin" in response.text
            finally:
                client.close()
        finally:
            monkeypatch.delitem(main.app.dependency_overrides, main.require_auth, raising=False)
            monkeypatch.delitem(main.app.dependency_overrides, get_session, raising=False)
            await engine.dispose()

    anyio.run(run_test)
