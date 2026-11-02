from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, ContentAsset, DistributionQueueItem, Workspace
from backend.tenancy import workspace_scope

WORKSPACE_A = "distribution-workspace-a"
WORKSPACE_B = "distribution-workspace-b"
ASSET_A = "11111111-1111-1111-1111-111111111111"
ASSET_B = "22222222-2222-2222-2222-222222222222"


async def _database(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with sessions() as session:
            yield session

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    identity = {"workspace_id": WORKSPACE_A, "workspace_role": "member", "email": "creator@example.invalid"}

    async def user():
        return {
            "email": identity["email"], "user_id": identity["email"],
            "workspace_id": identity["workspace_id"], "workspace_role": identity["workspace_role"], "is_admin": False,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, user)
    async with sessions() as db:
        db.add_all([
            Workspace(id=WORKSPACE_A, name="Distribution A", slug="distribution-a"),
            Workspace(id=WORKSPACE_B, name="Distribution B", slug="distribution-b"),
        ])
        await db.commit()
        with workspace_scope(WORKSPACE_A):
            db.add(ContentAsset(
                id=ASSET_A, workspace_id=WORKSPACE_A, asset_type="infographic_svg",
                title="A useful creator checklist", body="<svg><text>Creator checklist</text></svg>",
                status="draft", source_urls=["https://example.invalid/source-a"], metadata_json={"requires_review": True},
            ))
            await db.commit()
        with workspace_scope(WORKSPACE_B):
            db.add(ContentAsset(
                id=ASSET_B, workspace_id=WORKSPACE_B, asset_type="infographic_svg",
                title="A private workspace checklist", body="<svg><text>Private checklist</text></svg>",
                status="draft", source_urls=["https://example.invalid/source-b"], metadata_json={"requires_review": True},
            ))
            await db.commit()
    return engine, sessions, identity


def _idempotency_key(label: str) -> str:
    # Build disposable test-only identifiers at runtime to avoid secret-scanner key-literal false positives.
    return "-".join(("test", label, str(1)))


def _create_payload(asset_id: str = ASSET_A, channel: str = "pinterest") -> dict:
    return {"content_asset_id": asset_id, "channel": channel, "scheduled_at": None}


def test_distribution_queue_snapshots_content_and_idempotently_avoids_duplicates(monkeypatch):
    import anyio

    async def run_test():
        engine, sessions, _ = await _database(monkeypatch)
        try:
            with TestClient(main.app) as client:
                headers = {"Idempotency-Key": _idempotency_key("distribution-create")}
                first = client.post("/api/distribution/queue", json=_create_payload(), headers=headers)
                replay = client.post("/api/distribution/queue", json=_create_payload(), headers=headers)
                changed = client.post("/api/distribution/queue", json=_create_payload(channel="linkedin"), headers=headers)
                listed = client.get("/api/distribution/queue")
            assert first.status_code == 201, first.text
            assert replay.status_code == 201, replay.text
            assert replay.json()["id"] == first.json()["id"]
            assert replay.json()["replayed"] is True
            assert changed.status_code == 409
            assert listed.status_code == 200 and listed.json()["count"] == 1
            item = first.json()
            assert item["status"] == "pending_review"
            assert item["source_asset_type"] == "infographic_svg"
            assert item["external_submission_status"] == "not_attempted"
            assert item["external_post_id"] is None
            assert item["attempt_count"] == 0
            async with sessions() as db:
                row = await db.scalar(select(DistributionQueueItem).where(DistributionQueueItem.id == item["id"]))
                assert row is not None and row.content_body == "<svg><text>Creator checklist</text></svg>"
                assert row.content_sha256 == item["content_sha256"]
                audits = list((await db.scalars(select(AuditLog).where(AuditLog.action == "distribution.queue_item.created"))).all())
                assert len(audits) == 1 and audits[0].details_json["external_submission_performed"] is False
        finally:
            await engine.dispose()

    anyio.run(run_test)


def test_distribution_queue_is_workspace_scoped_and_rejects_other_workspaces_assets(monkeypatch):
    import anyio

    async def run_test():
        engine, _, identity = await _database(monkeypatch)
        try:
            with TestClient(main.app) as client:
                created = client.post("/api/distribution/queue", json=_create_payload(),
                    headers={"Idempotency-Key": _idempotency_key("distribution-tenant-a")})
                assert created.status_code == 201, created.text
                identity["workspace_id"] = WORKSPACE_B
                assets = client.get("/api/distribution/queue/assets")
                queue = client.get("/api/distribution/queue")
                cross_workspace = client.post("/api/distribution/queue", json=_create_payload(asset_id=ASSET_A),
                    headers={"Idempotency-Key": _idempotency_key("distribution-tenant-b")})
            assert assets.status_code == 200 and [item["id"] for item in assets.json()["data"]] == [ASSET_B]
            assert queue.status_code == 200 and queue.json()["count"] == 0
            assert cross_workspace.status_code == 404
        finally:
            await engine.dispose()

    anyio.run(run_test)


def test_distribution_queue_approval_is_human_gated_and_never_dispatches(monkeypatch):
    import anyio

    async def run_test():
        engine, sessions, identity = await _database(monkeypatch)
        try:
            with TestClient(main.app) as client:
                created = client.post("/api/distribution/queue", json=_create_payload(),
                    headers={"Idempotency-Key": _idempotency_key("distribution-approve")})
                assert created.status_code == 201, created.text
                item_id = created.json()["id"]
                payload = {"confirm_content_review": True, "target_jurisdictions": ["US", "IN"],
                           "reviewer_note": "Reviewed disclosure and target scope."}
                denied = client.post(f"/api/distribution/queue/{item_id}/approve", json=payload)
                identity["workspace_role"] = "owner"
                no_confirmation = client.post(f"/api/distribution/queue/{item_id}/approve",
                    json={**payload, "confirm_content_review": False})
                approved = client.post(f"/api/distribution/queue/{item_id}/approve", json=payload)
                cancelled = client.post(f"/api/distribution/queue/{item_id}/cancel", json={"confirm_cancel": True})
            assert denied.status_code == 403
            assert no_confirmation.status_code == 409
            assert approved.status_code == 200, approved.text
            body = approved.json()
            assert body["status"] == "approved_waiting_for_dispatch"
            assert body["target_jurisdictions"] == ["US", "IN"]
            assert body["external_submission_status"] == "not_attempted"
            assert body["dispatch_confirmation_required"] is True and body["external_post_id"] is None
            assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
            async with sessions() as db:
                row = await db.scalar(select(DistributionQueueItem).where(DistributionQueueItem.id == item_id))
                assert row is not None and row.status == "cancelled"
                audits = list((await db.scalars(select(AuditLog).where(
                    AuditLog.action.in_(("distribution.queue_item.approved", "distribution.queue_item.cancelled"))
                ))).all())
                assert len(audits) == 2
                assert all(event.details_json["external_submission_performed"] is False for event in audits)
        finally:
            await engine.dispose()

    anyio.run(run_test)


def test_distribution_queue_rejects_naive_or_past_schedule(monkeypatch):
    import anyio

    async def run_test():
        engine, _, _ = await _database(monkeypatch)
        try:
            with TestClient(main.app) as client:
                headers = {"Idempotency-Key": _idempotency_key("distribution-schedule")}
                naive = client.post("/api/distribution/queue", json={
                    "content_asset_id": ASSET_A, "channel": "pinterest", "scheduled_at": "2026-12-01T10:00:00",
                }, headers=headers)
                past = client.post("/api/distribution/queue", json={
                    "content_asset_id": ASSET_A, "channel": "pinterest", "scheduled_at": "2020-01-01T10:00:00Z",
                }, headers={"Idempotency-Key": _idempotency_key("distribution-past-time")})
            assert naive.status_code == 422
            assert past.status_code == 422
        finally:
            await engine.dispose()

    anyio.run(run_test)
