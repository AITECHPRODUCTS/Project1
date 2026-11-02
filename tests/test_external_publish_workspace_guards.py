from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, PlatformExecutionControl, Workspace
from backend.tenancy import get_workspace_id


def _platform_admin(workspace_id: str | None = "publish-workspace"):
    async def current_user():
        return {
            "email": "platform-admin@example.invalid",
            "user_id": "platform-admin-user",
            "workspace_id": workspace_id,
            "workspace_role": "member",
            "is_admin": True,
        }
    return current_user


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
        db.add(PlatformExecutionControl(id=1, outbound_actions_paused=False))
        await db.commit()

    async def allow_compliance(*args, **kwargs):
        return object()

    # These tests focus on auth and provider-write behavior, while the dedicated
    # compliance suite exercises real evidence matching and approval enforcement.
    monkeypatch.setattr(main, "_require_live_compliance_approval", allow_compliance, raising=False)
    return engine, sessions


def _cms_payload(**overrides):
    payload = {
        "provider": "wordpress",
        "title": "A reviewed affiliate article",
        "article_html": "<html><body><p>This is a sufficiently long reviewed draft article.</p></body></html>",
        "canonical_url": "https://example.com/article",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_external_publish_and_landing_routes_require_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(401, "Authentication required")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    with TestClient(main.app) as client:
        social = client.post("/api/social/publish", json={"platform": "reddit", "post": {"title": "x", "text": "y"}})
        landing = client.post("/api/landing/page", json={
            "headline": "Useful resource",
            "subheadline": "A short and honest guide",
            "benefit_bullets": ["Learn the basics"],
            "privacy_url": "https://example.com/privacy",
        })
        cms = client.post("/api/cms/publish", json=_cms_payload())
    assert social.status_code == 401
    assert landing.status_code == 401
    assert cms.status_code == 401


def test_workspace_admin_cannot_use_global_social_or_cms_provider_credentials(monkeypatch):
    async def workspace_owner():
        return {
            "email": "owner@example.invalid",
            "user_id": "workspace-owner",
            "workspace_id": "owner-workspace",
            "workspace_role": "owner",
            "is_admin": False,
        }

    called = []

    async def social(*args, **kwargs):
        called.append("social")
        return {"status": "published"}

    async def cms(*args, **kwargs):
        called.append("cms")
        return {"status": "publish"}

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, workspace_owner)
    monkeypatch.setattr(main, "social_media_scheduler", social)
    monkeypatch.setattr(main, "publish_article", cms)
    with TestClient(main.app) as client:
        social_response = client.post("/api/social/publish", json={
            "platform": "reddit", "post": {"subreddit": "test", "title": "title", "text": "body"},
            "confirm_live_publish": True,
        })
        cms_response = client.post("/api/cms/publish", json=_cms_payload())
    assert social_response.status_code == 403
    assert cms_response.status_code == 403
    assert called == []


def test_landing_page_refuses_token_issuance_without_a_selected_workspace(monkeypatch):
    async def no_workspace():
        return {
            "email": "owner@example.invalid",
            "user_id": "owner-user",
            "workspace_id": None,
            "workspace_role": "owner",
            "is_admin": False,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    with TestClient(main.app) as client:
        response = client.post("/api/landing/page", json={
            "headline": "Useful resource",
            "subheadline": "A short and honest guide",
            "benefit_bullets": ["Learn the basics"],
            "privacy_url": "https://example.com/privacy",
        })
    assert response.status_code == 403


def test_landing_token_is_generated_for_authenticated_workspace(monkeypatch):
    workspace_id = "landing-token-workspace"
    generated = {}

    async def owner():
        return {
            "email": "owner@example.invalid",
            "user_id": "landing-owner",
            "workspace_id": workspace_id,
            "workspace_role": "owner",
            "is_admin": False,
        }

    def token_for(selected_workspace, purpose):
        generated.update({"workspace_id": selected_workspace, "purpose": purpose, "active_workspace": get_workspace_id()})
        return "test-signed-token"

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, owner)
    monkeypatch.setattr(main, "issue_workspace_token", token_for)
    monkeypatch.setattr(main, "squeeze_page_builder", lambda **kwargs: f"<html>{kwargs['workspace_token']}</html>")
    with TestClient(main.app) as client:
        response = client.post("/api/landing/page", json={
            "headline": "Useful resource",
            "subheadline": "A short and honest guide",
            "benefit_bullets": ["Learn the basics"],
            "privacy_url": "https://example.com/privacy",
        })
    assert response.status_code == 200
    assert "test-signed-token" in response.text
    assert generated == {
        "workspace_id": workspace_id,
        "purpose": "lead_capture",
        "active_workspace": workspace_id,
    }


@pytest.mark.asyncio
async def test_social_live_publish_requires_explicit_confirmation_and_writes_audit(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        workspace_id = "publish-workspace"
        async with sessions() as db:
            db.add(Workspace(id=workspace_id, name="Publish workspace", slug="publish-workspace"))
            await db.commit()

        monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, _platform_admin(workspace_id))
        monkeypatch.setattr(main.settings, "publishing_dry_run", False)
        calls = []

        async def fake_publish(platform, post):
            calls.append((platform, post))
            return {"status": "published", "platform": platform, "remote_id": "remote-123"}

        monkeypatch.setattr(main, "social_media_scheduler", fake_publish)
        with TestClient(main.app) as client:
            denied = client.post("/api/social/publish", json={
                "platform": "reddit",
                "post": {"subreddit": "test", "title": "Reviewed", "text": "Body"},
            })
            approved = client.post(
                "/api/social/publish",
                json={
                    "platform": "reddit",
                    "post": {"subreddit": "test", "title": "Reviewed", "text": "Body"},
                    "confirm_live_publish": True,
                    "target_jurisdictions": ["US"],
                },
                headers={"Idempotency-Key": "social-publish-test-key-0001"},
            )

        assert denied.status_code == 409
        assert approved.status_code == 200
        assert approved.json()["remote_id"] == "remote-123"
        assert calls == [("reddit", {"subreddit": "test", "title": "Reviewed", "text": "Body"})]
        async with sessions() as db:
            event = await db.scalar(select(AuditLog).where(AuditLog.action == "social_publish"))
        assert event is not None
        assert event.workspace_id == workspace_id
        assert event.outcome == "published"
        assert event.details_json["platform"] == "reddit"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cms_live_publish_requires_explicit_confirmation_and_writes_audit(monkeypatch):
    engine, sessions = await _database(monkeypatch)
    try:
        workspace_id = "cms-publish-workspace"
        async with sessions() as db:
            db.add(Workspace(id=workspace_id, name="CMS workspace", slug="cms-publish-workspace"))
            await db.commit()

        monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, _platform_admin(workspace_id))
        calls = []

        async def fake_publish(**kwargs):
            calls.append(kwargs)
            return {"status": "publish", "provider": kwargs["provider"], "remote_id": "cms-remote-1"}

        monkeypatch.setattr(main, "publish_article", fake_publish)
        payload = _cms_payload(status="publish")
        with TestClient(main.app) as client:
            denied = client.post("/api/cms/publish", json=payload)
            approved = client.post("/api/cms/publish", json={**payload, "confirm_live_publish": True}, headers={"Idempotency-Key": "cms-publish-test-key-0001"})

        assert denied.status_code == 409
        assert approved.status_code == 200
        assert calls and calls[0]["status"] == "publish"
        async with sessions() as db:
            event = await db.scalar(select(AuditLog).where(AuditLog.action == "cms_publish"))
        assert event is not None
        assert event.workspace_id == workspace_id
        assert event.outcome == "publish"
    finally:
        await engine.dispose()
