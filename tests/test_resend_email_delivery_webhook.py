from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend import main
from backend.database import Base, get_session
from backend.models import EmailDeliveryEvent, Lead, LeadConsentEvent, ScheduledEmail, Workspace
from backend.services.resend_email_events import is_resend_webhook_secret_configured, verify_resend_webhook_signature
from backend.tenancy import workspace_scope


RAW_SECRET = b"resend-webhook-test-secret-material-32"
WEBHOOK_SECRET = "whsec_" + base64.b64encode(RAW_SECRET).decode("ascii")
OBSERVED_AT = datetime(2026, 10, 29, 7, 0, tzinfo=timezone.utc)


def _signed_headers(body: bytes, *, event_id: str = "evt-test-0001", timestamp: int | None = None):
    ts = str(int(time.time()) if timestamp is None else timestamp)
    signed = event_id.encode() + b"." + ts.encode() + b"." + body
    signature = base64.b64encode(hmac.new(RAW_SECRET, signed, hashlib.sha256).digest()).decode("ascii")
    return {"svix-id": event_id, "svix-timestamp": ts, "svix-signature": "v1," + signature}


def test_resend_signature_verification_uses_raw_body_and_rejects_stale_signatures():
    body = b'{"type":"email.delivered","data":{"email_id":"re_msg_123","to":["reader@example.test"]}}'
    headers = _signed_headers(body)
    assert is_resend_webhook_secret_configured(WEBHOOK_SECRET)
    assert verify_resend_webhook_signature(
        body, secret=WEBHOOK_SECRET, svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"], svix_signature=headers["svix-signature"],
    )
    assert not verify_resend_webhook_signature(
        body + b" ", secret=WEBHOOK_SECRET, svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"], svix_signature=headers["svix-signature"],
    )
    stale_headers = _signed_headers(body, timestamp=int(time.time()) - 600)
    assert not verify_resend_webhook_signature(
        body, secret=WEBHOOK_SECRET, svix_id=stale_headers["svix-id"],
        svix_timestamp=stale_headers["svix-timestamp"], svix_signature=stale_headers["svix-signature"],
    )
    assert not is_resend_webhook_secret_configured("not-a-svix-secret")


async def _database(tmp_path):
    engine = create_async_engine(
        "sqlite+aiosqlite:///" + str(tmp_path / "resend-events.sqlite3"),
        poolclass=NullPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        workspace = Workspace(name="Resend events workspace", slug="resend-events-workspace")
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        with workspace_scope(workspace_id):
            lead = Lead(
                workspace_id=workspace_id, email="reader@example.test",
                consent_at=OBSERVED_AT, consent_source="persisted_landing_page",
                lead_magnet="Guide",
            )
            db.add(lead)
            await db.flush()
            sent = ScheduledEmail(
                workspace_id=workspace_id, lead_id=lead.id, sequence_day=0,
                subject="Your guide", body_html="<p>Your guide</p>", body_text="Your guide",
                condition_json={"requires_consent": True}, send_at=OBSERVED_AT,
                status="sent", provider_message_id="re_msg_scheduled_123",
            )
            pending = ScheduledEmail(
                workspace_id=workspace_id, lead_id=lead.id, sequence_day=1,
                subject="Follow-up", body_html="<p>Follow-up</p>", body_text="Follow-up",
                condition_json={"requires_consent": True}, send_at=OBSERVED_AT, status="scheduled",
            )
            db.add_all([sent, pending])
            await db.flush()
            result = {
                "workspace_id": workspace_id, "lead_id": lead.id,
                "sent_id": sent.id, "pending_id": pending.id,
            }
            await db.commit()
    return engine, sessions, result


def _payload(event_type: str, *, message_id: str = "re_msg_scheduled_123", extra: dict | None = None):
    data = {
        "email_id": message_id,
        "to": ["reader@example.test"],
        "created_at": "2026-10-29T07:00:00.000Z",
    }
    data.update(extra or {})
    return json.dumps(
        {"type": event_type, "created_at": "2026-10-29T07:00:00.000Z", "data": data},
        separators=(",", ":"),
    ).encode()


def _client(monkeypatch, sessions):
    async def override_get_session():
        async with sessions() as db:
            yield db
    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_get_session)
    monkeypatch.setattr(main.settings, "resend_webhook_secret", WEBHOOK_SECRET)
    return TestClient(main.app)


def _post(client, raw_body: bytes, event_id: str):
    headers = {"content-type": "application/json", **_signed_headers(raw_body, event_id=event_id)}
    return client.post("/api/webhooks/resend/email-events", content=raw_body, headers=headers)


def test_resend_delivered_event_is_correlated_and_deduplicated(tmp_path, monkeypatch):
    engine, sessions, seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    try:
        body = _payload("email.delivered")
        first = _post(client, body, "evt-delivered-0001")
        duplicate = _post(client, body, "evt-delivered-0001")
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "processed"
        assert duplicate.status_code == 200
        assert duplicate.json()["status"] == "duplicate_ignored"

        async def inspect():
            async with sessions() as db:
                with workspace_scope(seeded["workspace_id"]):
                    sent = await db.get(ScheduledEmail, seeded["sent_id"])
                    events = list((await db.scalars(select(EmailDeliveryEvent))).all())
                return sent, events
        sent, events = asyncio.run(inspect())
        assert sent is not None and sent.status == "delivered"
        assert len(events) == 1 and events[0].outcome == "delivered"
        assert "reader@example.test" not in json.dumps(events[0].metadata_json)
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())


def test_resend_hard_bounce_suppresses_pending_mail_without_fake_unsubscribe(tmp_path, monkeypatch):
    engine, sessions, seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    try:
        body = _payload("email.bounced", extra={"bounce": {"type": "Permanent", "subType": "Suppressed"}})
        response = _post(client, body, "evt-bounced-0001")
        assert response.status_code == 200, response.text
        assert response.json()["suppression_applied"] is True

        async def inspect():
            async with sessions() as db:
                with workspace_scope(seeded["workspace_id"]):
                    lead = await db.get(Lead, seeded["lead_id"])
                    sent = await db.get(ScheduledEmail, seeded["sent_id"])
                    pending = await db.get(ScheduledEmail, seeded["pending_id"])
                    events = list((await db.scalars(select(EmailDeliveryEvent))).all())
                return lead, sent, pending, events
        lead, sent, pending, events = asyncio.run(inspect())
        assert lead is not None and lead.email_suppression_reason == "hard_bounce"
        assert lead.email_suppressed_at is not None
        assert lead.unsubscribed_at is None, "A hard bounce is not a recipient unsubscribe"
        assert sent is not None and sent.status == "bounced"
        assert pending is not None and pending.status == "suppressed"
        assert len(events) == 1
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())


def test_resend_complaint_suppresses_and_records_consent_withdrawal_once(tmp_path, monkeypatch):
    engine, sessions, seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    try:
        body = _payload("email.complained")
        response = _post(client, body, "evt-complaint-0001")
        assert response.status_code == 200, response.text

        async def inspect():
            async with sessions() as db:
                with workspace_scope(seeded["workspace_id"]):
                    lead = await db.get(Lead, seeded["lead_id"])
                    pending = await db.get(ScheduledEmail, seeded["pending_id"])
                    events = list((await db.scalars(select(EmailDeliveryEvent))).all())
                    consent = list((await db.scalars(select(LeadConsentEvent))).all())
                return lead, pending, events, consent
        lead, pending, events, consent = asyncio.run(inspect())
        assert lead is not None and lead.email_suppression_reason == "spam_complaint"
        assert lead.email_suppressed_at is not None and lead.unsubscribed_at is not None
        assert pending is not None and pending.status == "suppressed"
        assert len(events) == 1 and events[0].outcome == "complained"
        assert len(consent) == 1 and consent[0].source == "resend_complaint_webhook"
        assert "reader@example.test" not in json.dumps(events[0].metadata_json)

        duplicate = _post(client, body, "evt-complaint-0001")
        assert duplicate.status_code == 200 and duplicate.json()["status"] == "duplicate_ignored"

        async def count_rows():
            async with sessions() as db:
                with workspace_scope(seeded["workspace_id"]):
                    return (
                        len(list((await db.scalars(select(EmailDeliveryEvent))).all())),
                        len(list((await db.scalars(select(LeadConsentEvent))).all())),
                    )
        assert asyncio.run(count_rows()) == (1, 1)
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())


def test_resend_webhook_fails_closed_without_secret_or_with_bad_signature(tmp_path, monkeypatch):
    engine, sessions, _seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    try:
        body = _payload("email.delivered")
        monkeypatch.setattr(main.settings, "resend_webhook_secret", "")
        missing = client.post(
            "/api/webhooks/resend/email-events", content=body,
            headers={"content-type": "application/json"},
        )
        assert missing.status_code == 503
        monkeypatch.setattr(main.settings, "resend_webhook_secret", WEBHOOK_SECRET)
        invalid = client.post("/api/webhooks/resend/email-events", content=body, headers={
            "content-type": "application/json", "svix-id": "evt-invalid-sig-01",
            "svix-timestamp": str(int(time.time())), "svix-signature": "v1,invalid",
        })
        assert invalid.status_code == 401
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())
