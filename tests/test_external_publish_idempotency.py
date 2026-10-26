from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import ExternalAction, Workspace


WORKSPACE_ID = "external-action-workspace"


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
    async with sessions() as db:
        db.add(Workspace(id=WORKSPACE_ID, name="External action workspace", slug="external-action-workspace"))
        await db.commit()

    async def platform_admin():
        return {
            "email": "platform-admin@example.invalid",
            "user_id": "platform-admin-user",
            "workspace_id": WORKSPACE_ID,
            "workspace_role": "member",
            "is_admin": True,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, platform_admin)
    monkeypatch.setattr(main.settings, "publishing_dry_run", False)
    return engine, sessions


def _social_payload(**overrides):
    payload = {
        "platform": "reddit",
        "post": {"subreddit": "test", "title": "A reviewed draft", "text": "A compliant example post."},
        "confirm_live_publish": True,
    }
    payload.update(overrides)
    return payload


def _cms_payload(**overrides):
    payload = {
        "provider": "wordpress",
        "title": "Reviewed draft article",
        "article_html": "<html><body><p>A sufficiently long reviewed article draft.</p></body></html>",
        "canonical_url": "https://example.com/reviewed-article",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_live_social_publish_replays_completed_action_without_provider_duplicate(monkeypatch):
    async def run_test():
        engine, sessions = await _database(monkeypatch)
        calls: list[tuple[str, dict[str, Any]]] = []

        async def fake_publish(platform, post):
            calls.append((platform, post))
            return {"status": "published", "platform": platform, "remote_id": "reddit-post-123", "url": "https://reddit.example/post/123"}

        monkeypatch.setattr(main, "social_media_scheduler", fake_publish)
        payload = _social_payload()
        key = "social-publish-key-0001"
        try:
            with TestClient(main.app) as client:
                first = client.post("/api/social/publish", json=payload, headers={"Idempotency-Key": key})
                replay = client.post("/api/social/publish", json=payload, headers={"Idempotency-Key": key})
                changed = client.post("/api/social/publish", json=_social_payload(post={"subreddit": "test", "title": "Changed", "text": "Different post"}), headers={"Idempotency-Key": key})
            assert first.status_code == 200, first.text
            assert replay.status_code == 200, replay.text
            assert replay.json() == first.json()
            assert changed.status_code == 409
            assert len(calls) == 1
            async with sessions() as db:
                records = list((await db.scalars(select(ExternalAction))).all())
            assert len(records) == 1
            assert records[0].status == "completed"
            assert records[0].remote_id == "reddit-post-123"
            assert records[0].workspace_id == WORKSPACE_ID
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)


def test_external_provider_writes_require_idempotency_key(monkeypatch):
    async def run_test():
        engine, _ = await _database(monkeypatch)
        called: list[str] = []

        async def fake_social(*args, **kwargs):
            called.append("social")
            return {"status": "published"}

        async def fake_cms(**kwargs):
            called.append("cms")
            return {"status": "draft"}

        monkeypatch.setattr(main, "social_media_scheduler", fake_social)
        monkeypatch.setattr(main, "publish_article", fake_cms)
        try:
            with TestClient(main.app) as client:
                social = client.post("/api/social/publish", json=_social_payload())
                cms = client.post("/api/cms/publish", json=_cms_payload())
            assert social.status_code == 428
            assert cms.status_code == 428
            assert called == []
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)


def test_cms_publish_replays_completed_draft_write_with_same_idempotency_key(monkeypatch):
    async def run_test():
        engine, sessions = await _database(monkeypatch)
        calls: list[dict[str, Any]] = []

        async def fake_cms(**kwargs):
            calls.append(kwargs)
            return {"provider": "wordpress", "status": "draft", "remote_id": "cms-post-456", "url": "https://example.com/?p=456"}

        monkeypatch.setattr(main, "publish_article", fake_cms)
        key = "cms-publish-key-0001"
        payload = _cms_payload()
        try:
            with TestClient(main.app) as client:
                first = client.post("/api/cms/publish", json=payload, headers={"Idempotency-Key": key})
                replay = client.post("/api/cms/publish", json=payload, headers={"Idempotency-Key": key})
            assert first.status_code == 200, first.text
            assert replay.status_code == 200, replay.text
            assert replay.json() == first.json()
            assert len(calls) == 1
            async with sessions() as db:
                record = await db.scalar(select(ExternalAction).where(ExternalAction.action_type == "cms_publish"))
            assert record is not None
            assert record.status == "completed"
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)


def test_unknown_live_publish_outcome_blocks_same_or_changed_key_replay(monkeypatch):
    async def run_test():
        engine, sessions = await _database(monkeypatch)
        calls = 0

        async def fail_after_send_attempt(platform, post):
            nonlocal calls
            calls += 1
            raise ConnectionError("provider connection dropped after sending request")

        monkeypatch.setattr(main, "social_media_scheduler", fail_after_send_attempt)
        key = "social-publish-unknown-0001"
        payload = _social_payload()
        try:
            with TestClient(main.app, raise_server_exceptions=False) as client:
                first = client.post("/api/social/publish", json=payload, headers={"Idempotency-Key": key})
                replay_same_key = client.post("/api/social/publish", json=payload, headers={"Idempotency-Key": key})
                replay_new_key = client.post("/api/social/publish", json=payload, headers={"Idempotency-Key": "social-publish-unknown-0002"})
            assert first.status_code == 500
            assert replay_same_key.status_code == 409
            assert replay_new_key.status_code == 409
            assert calls == 1
            async with sessions() as db:
                action = await db.scalar(select(ExternalAction).where(ExternalAction.idempotency_key == key))
            assert action is not None and action.status == "unknown"
            assert action.error_type == "ConnectionError"
        finally:
            await engine.dispose()
    import anyio
    anyio.run(run_test)
