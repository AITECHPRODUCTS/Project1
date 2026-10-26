from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models import Lead, ScheduledEmail, Workspace
from backend.services import email_delivery
from backend.tenancy import workspace_scope


def _settings():
    return SimpleNamespace(
        resend_api_key="re_test_key",
        resend_from_email="Affiliate Updates <sender@example.test>",
        app_public_url="https://app.example.test",
        tracking_hmac_secret="t" * 40,
        app_session_secret="s" * 40,
    )


async def _database(tmp_path, monkeypatch):
    db_path = tmp_path / "scheduled-email-claims.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"timeout": 10},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(email_delivery, "SessionLocal", sessions)
    monkeypatch.setattr(email_delivery, "get_settings", _settings)
    return engine, sessions


async def _seed_email(sessions, *, status="scheduled", claimed_at=None, age_minutes=2):
    now = datetime.now(timezone.utc)
    async with sessions() as db:
        workspace = Workspace(name="Email claims workspace", slug=f"email-claims-{datetime.now(timezone.utc).timestamp()}")
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        lead = Lead(
            workspace_id=workspace_id,
            email="subscriber@example.test",
            consent_at=now,
            consent_source="signup_form",
            lead_magnet="Starter guide",
        )
        db.add(lead)
        await db.flush()
        message = ScheduledEmail(
            workspace_id=workspace_id,
            lead_id=lead.id,
            sequence_day=0,
            subject="Your starter guide",
            body_text="Here is your guide.\n\nUnsubscribe: https://app.example.test/unsubscribe/lead?ts=123&sig=stable",
            body_html='<html><body><p>Here is your guide.</p><a href="https://app.example.test/unsubscribe/lead?ts=123&sig=stable">Unsubscribe</a></body></html>',
            condition_json={"requires_consent": True, "skip_if_unsubscribed": True},
            send_at=now - timedelta(minutes=age_minutes),
            status=status,
            claimed_at=claimed_at,
            attempts=0,
        )
        db.add(message)
        await db.commit()
        return workspace_id, lead.id, message.id


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"id": "resend-message-id"}


class _FakeClient:
    calls = []

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, *, json, headers):
        await asyncio.sleep(0.05)
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _Response()


@pytest.mark.asyncio
async def test_concurrent_workers_atomically_claim_and_send_a_due_email_once(tmp_path, monkeypatch):
    engine, sessions = await _database(tmp_path, monkeypatch)
    _FakeClient.calls = []
    monkeypatch.setattr("backend.services.email_delivery.httpx.AsyncClient", _FakeClient)
    try:
        workspace_id, _, message_id = await _seed_email(sessions)
        with workspace_scope(workspace_id):
            async with sessions() as first, sessions() as second:
                a, b = await asyncio.gather(
                    email_delivery.send_due_emails(first, workspace_id=workspace_id),
                    email_delivery.send_due_emails(second, workspace_id=workspace_id),
                )
        assert a["sent"] + b["sent"] == 1
        assert len(_FakeClient.calls) == 1
        call = _FakeClient.calls[0]
        assert call["url"] == "https://api.resend.com/emails"
        assert call["headers"]["Idempotency-Key"] == f"scheduled-email/{workspace_id}/{message_id}"
        assert call["json"]["headers"]["List-Unsubscribe"] == "<https://app.example.test/unsubscribe/lead?ts=123&sig=stable>"
        async with sessions() as db:
            row = await db.get(ScheduledEmail, message_id)
        assert row is not None
        assert row.status == "sent"
        assert row.claimed_at is None
        assert row.attempts == 1
        assert row.provider_message_id == "resend-message-id"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_delivery_lease_is_retried_with_same_idempotency_key(tmp_path, monkeypatch):
    engine, sessions = await _database(tmp_path, monkeypatch)
    _FakeClient.calls = []
    monkeypatch.setattr("backend.services.email_delivery.httpx.AsyncClient", _FakeClient)
    try:
        claimed_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        workspace_id, _, message_id = await _seed_email(
            sessions,
            status="sending",
            claimed_at=claimed_at,
            age_minutes=30,
        )
        with workspace_scope(workspace_id):
            async with sessions() as db:
                result = await email_delivery.send_due_emails(db, workspace_id=workspace_id)
        assert result["sent"] == 1
        assert len(_FakeClient.calls) == 1
        assert _FakeClient.calls[0]["headers"]["Idempotency-Key"] == f"scheduled-email/{workspace_id}/{message_id}"
        async with sessions() as db:
            row = await db.get(ScheduledEmail, message_id)
        assert row is not None and row.status == "sent" and row.claimed_at is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_delivery_older_than_provider_dedup_window_requires_manual_review(tmp_path, monkeypatch):
    engine, sessions = await _database(tmp_path, monkeypatch)
    _FakeClient.calls = []
    monkeypatch.setattr("backend.services.email_delivery.httpx.AsyncClient", _FakeClient)
    try:
        claimed_at = datetime.now(timezone.utc) - timedelta(hours=24)
        workspace_id, _, message_id = await _seed_email(
            sessions,
            status="sending",
            claimed_at=claimed_at,
            age_minutes=60,
        )
        with workspace_scope(workspace_id):
            async with sessions() as db:
                result = await email_delivery.send_due_emails(db, workspace_id=workspace_id)
        assert result["sent"] == 0
        assert _FakeClient.calls == []
        async with sessions() as db:
            row = await db.get(ScheduledEmail, message_id)
        assert row is not None
        assert row.status == "delivery_unknown"
        assert row.claimed_at is None
        assert "manual reconciliation" in (row.last_error or "")
    finally:
        await engine.dispose()
