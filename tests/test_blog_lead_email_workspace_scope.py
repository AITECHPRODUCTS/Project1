from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import ContentAsset, Lead, ScheduledEmail, Workspace
from backend.services import email_delivery
from backend.tenancy import get_workspace_id, workspace_scope


async def _database(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(email_delivery, "SessionLocal", sessions)

    async def override_session():
        async with sessions() as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    return engine, sessions


async def _create_workspaces(sessions):
    async with sessions() as db:
        a = Workspace(name="Lead Workspace A", slug="lead-workspace-a")
        b = Workspace(name="Lead Workspace B", slug="lead-workspace-b")
        db.add_all([a, b])
        await db.flush()
        result = (a.id, b.id)
        await db.commit()
    return result


def _capture_payload():
    return {
        "email": "same-subscriber@example.invalid",
        "consent": True,
        "lead_magnet": "A practical starter guide",
        "audience": "affiliate marketers",
        "offer": {"name": "Example product", "affiliate_url": "https://example.com/offer"},
        "consent_source": "workspace_form",
    }


@pytest.mark.asyncio
async def test_lead_sequence_is_isolated_and_idempotent_per_workspace(monkeypatch):
    engine, sessions = await _database(monkeypatch)

    async def fake_complete(*args, **kwargs):
        return {"text": json.dumps([]), "provider": "test-provider"}

    monkeypatch.setattr(email_delivery.llm_service, "complete", fake_complete)
    try:
        workspace_a, workspace_b = await _create_workspaces(sessions)
        payload = _capture_payload()
        async with sessions() as db:
            with workspace_scope(workspace_a):
                result_a = await email_delivery.capture_lead_and_schedule(
                    db,
                    email_address=payload["email"],
                    consent=payload["consent"],
                    lead_magnet=payload["lead_magnet"],
                    audience=payload["audience"],
                    offer=payload["offer"],
                    consent_source=payload["consent_source"],
                    workspace_id=workspace_a,
                )
        async with sessions() as db:
            with workspace_scope(workspace_b):
                result_b = await email_delivery.capture_lead_and_schedule(
                    db,
                    email_address=payload["email"],
                    consent=payload["consent"],
                    lead_magnet=payload["lead_magnet"],
                    audience=payload["audience"],
                    offer=payload["offer"],
                    consent_source=payload["consent_source"],
                    workspace_id=workspace_b,
                )
        async with sessions() as db:
            with workspace_scope(workspace_a):
                duplicate_a = await email_delivery.capture_lead_and_schedule(
                    db,
                    email_address=payload["email"],
                    consent=payload["consent"],
                    lead_magnet=payload["lead_magnet"],
                    audience=payload["audience"],
                    offer=payload["offer"],
                    consent_source=payload["consent_source"],
                    workspace_id=workspace_a,
                )

        assert result_a["workspace_id"] == workspace_a
        assert result_b["workspace_id"] == workspace_b
        assert result_a["lead_id"] != result_b["lead_id"]
        assert result_a["emails_scheduled"] == 5
        assert result_b["emails_scheduled"] == 5
        assert duplicate_a["lead_id"] == result_a["lead_id"]
        assert duplicate_a["emails_scheduled"] == 0

        async with sessions() as db:
            leads = list((await db.scalars(select(Lead))).all())
            emails = list((await db.scalars(select(ScheduledEmail))).all())
        assert {(lead.workspace_id, lead.email) for lead in leads} == {
            (workspace_a, payload["email"]),
            (workspace_b, payload["email"]),
        }
        assert len(emails) == 10
        assert {email.workspace_id for email in emails} == {workspace_a, workspace_b}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_email_helpers_fail_closed_without_workspace_context():
    with workspace_scope(None):
        with pytest.raises(ValueError, match="Authorized workspace context required"):
            await email_delivery.capture_lead_and_schedule(
                SimpleNamespace(),
                email_address="subscriber@example.invalid",
                consent=True,
                lead_magnet="Starter guide",
                audience="subscribers",
                offer={},
            )
        with pytest.raises(ValueError, match="Authorized workspace context required"):
            await email_delivery.send_due_emails()


def test_blog_route_requires_workspace_before_generating_or_saving(monkeypatch):
    calls = []

    async def fake_blog_builder(*args, **kwargs):
        calls.append(get_workspace_id())
        return {
            "title": "A safe draft",
            "html": "<p>Review before publishing</p>",
            "rag_sources": [],
            "word_count": 1500,
            "schema_types": ["Article"],
            "provider": "test-provider",
        }

    monkeypatch.setattr(main, "affiliate_blog_builder", fake_blog_builder)
    db = SimpleNamespace(add=Mock(), commit=AsyncMock())

    async def no_workspace():
        return {
            "email": "unscoped@example.invalid",
            "user_id": "unscoped-blog-user",
            "workspace_id": None,
            "workspace_role": "member",
            "is_admin": False,
        }

    async def override_session():
        yield db

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/content/blog", json={"topic": "safe affiliate guide"})
        assert response.status_code == 403
        assert calls == []
        db.add.assert_not_called()
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)
        main.app.dependency_overrides.pop(get_session, None)


def test_blog_asset_is_explicitly_bound_to_authenticated_workspace(monkeypatch):
    workspace_id = "blog-workspace-test"
    observed = []
    added = []

    async def fake_blog_builder(*args, **kwargs):
        observed.append(get_workspace_id())
        return {
            "title": "A safe draft",
            "html": "<p>Review before publishing</p>",
            "rag_sources": [],
            "word_count": 1500,
            "schema_types": ["Article"],
            "provider": "test-provider",
        }

    async def auth_workspace():
        return {
            "email": "author@example.invalid",
            "user_id": "blog-author",
            "workspace_id": workspace_id,
            "workspace_role": "owner",
            "is_admin": False,
        }

    class FakeSession:
        def add(self, row):
            added.append(row)

        async def commit(self):
            return None

    async def override_session():
        yield FakeSession()

    monkeypatch.setattr(main, "affiliate_blog_builder", fake_blog_builder)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, auth_workspace)
    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/content/blog", json={"topic": "safe affiliate guide"})
        assert response.status_code == 200, response.text
        asset = next(row for row in added if isinstance(row, ContentAsset))
        assert asset.workspace_id == workspace_id
        assert observed == [workspace_id]
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)
        main.app.dependency_overrides.pop(get_session, None)


def test_private_lead_capture_requires_authenticated_workspace(monkeypatch):
    called = []

    async def fake_create_lead(payload, db, *, workspace_id):
        called.append((workspace_id, get_workspace_id()))
        return {"workspace_id": workspace_id, "emails_scheduled": 5}

    async def no_workspace():
        return {
            "email": "unscoped@example.invalid",
            "user_id": "unscoped-lead-user",
            "workspace_id": None,
            "workspace_role": "member",
            "is_admin": False,
        }

    async def override_session():
        yield SimpleNamespace()

    monkeypatch.setattr(main, "create_lead", fake_create_lead)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/leads/capture", json=_capture_payload())
        assert response.status_code == 403
        assert called == []
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)
        main.app.dependency_overrides.pop(get_session, None)


def test_public_lead_capture_requires_valid_purpose_bound_workspace_token(monkeypatch):
    called = []
    workspace_id = "public-lead-workspace"

    async def fake_create_lead(payload, db, *, workspace_id):
        called.append((workspace_id, get_workspace_id()))
        return {"workspace_id": workspace_id, "emails_scheduled": 5}

    async def override_session():
        yield SimpleNamespace()

    monkeypatch.setattr(main, "create_lead", fake_create_lead)
    monkeypatch.setattr(
        main,
        "verify_workspace_token",
        lambda token, purpose: workspace_id if token == "valid-token" and purpose == "lead_capture" else None,
    )
    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    try:
        with TestClient(main.app) as client:
            denied = client.post(
                "/api/public/leads/capture",
                json={**_capture_payload(), "workspace_token": "bad-token"},
            )
            accepted = client.post(
                "/api/public/leads/capture",
                json={**_capture_payload(), "workspace_token": "valid-token"},
                headers={"accept": "application/json"},
            )
        assert denied.status_code == 403
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["workspace_id"] == workspace_id
        assert called == [(workspace_id, workspace_id)]
    finally:
        main.app.dependency_overrides.pop(get_session, None)
