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


def test_resend_provider_model_default_matches_persisted_migration_default():
    provider_column = EmailDeliveryEvent.__table__.c.provider
    assert provider_column.server_default is not None
    assert "resend" in str(provider_column.server_default.arg)


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


def test_lead_email_delivery_history_is_workspace_scoped_and_pii_minimized(tmp_path, monkeypatch):
    engine, sessions, seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, lambda: {
        "user_id": "owner-a", "workspace_id": seeded["workspace_id"], "email": "owner@example.test",
    })
    try:
        async def seed_history():
            async with sessions() as db:
                with workspace_scope(seeded["workspace_id"]):
                    db.add(EmailDeliveryEvent(
                        workspace_id=seeded["workspace_id"],
                        lead_id=seeded["lead_id"],
                        provider="resend",
                        provider_event_id="evt-history-bounce-0001",
                        provider_message_id="re_msg_scheduled_123",
                        scheduled_email_id=seeded["sent_id"],
                        event_type="email.bounced",
                        outcome="bounced",
                        event_created_at=OBSERVED_AT,
                        payload_sha256="a" * 64,
                        metadata_json={
                            "recipient_count": 1,
                            "bounce_type": "permanent",
                            "bounce_subtype": "mailbox_unavailable",
                            "unsafe_payload_field": "must-not-leak",
                        },
                        received_at=OBSERVED_AT,
                    ))
                other_workspace = Workspace(
                    name="Other delivery-history workspace",
                    slug="other-delivery-history-workspace",
                )
                db.add(other_workspace)
                await db.flush()
                with workspace_scope(other_workspace.id):
                    other_lead = Lead(
                        workspace_id=other_workspace.id,
                        email="other-reader@example.test",
                        consent_at=OBSERVED_AT,
                        consent_source="persisted_landing_page",
                        lead_magnet="Other guide",
                    )
                    db.add(other_lead)
                    await db.flush()
                    other_lead_id = other_lead.id
                await db.commit()
                return other_lead_id

        other_lead_id = asyncio.run(seed_history())
        response = client.get(f"/api/leads/{seeded['lead_id']}/email-delivery-events")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["read_only"] is True
        assert body["count"] == 1
        event = body["data"][0]
        assert event["provider"] == "resend"
        assert event["event_type"] == "email.bounced"
        assert event["outcome"] == "bounced"
        assert event["metadata"] == {
            "recipient_count": 1,
            "bounce_type": "permanent",
            "bounce_subtype": "mailbox_unavailable",
        }
        assert "provider_event_id" not in event
        assert "provider_message_id" not in event
        assert "payload_sha256" not in event
        assert "unsafe_payload_field" not in response.text
        assert "reader@example.test" not in response.text

        cross_workspace = client.get(f"/api/leads/{other_lead_id}/email-delivery-events")
        assert cross_workspace.status_code == 404
        invalid_limit = client.get(f"/api/leads/{seeded['lead_id']}/email-delivery-events?limit=0")
        assert invalid_limit.status_code == 422
        monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, lambda: {
            "user_id": "owner-a", "workspace_id": None, "email": "owner@example.test",
        })
        no_workspace = client.get(f"/api/leads/{seeded['lead_id']}/email-delivery-events")
        assert no_workspace.status_code == 403
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())


def test_resend_reused_event_id_with_different_signed_payload_is_conflict(tmp_path, monkeypatch):
    engine, sessions, seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    try:
        event_id = "evt-reused-payload-0001"
        delivered_body = _payload("email.delivered")
        first = _post(client, delivered_body, event_id)
        changed_body = _payload("email.delivery_delayed")
        conflicting = _post(client, changed_body, event_id)

        assert first.status_code == 200, first.text
        assert first.json()["status"] == "processed"
        assert conflicting.status_code == 409
        assert "conflicts" in conflicting.json()["detail"].lower()

        async def inspect():
            async with sessions() as db:
                with workspace_scope(seeded["workspace_id"]):
                    sent = await db.get(ScheduledEmail, seeded["sent_id"])
                    events = list((await db.scalars(select(EmailDeliveryEvent))).all())
                return sent, events

        sent, events = asyncio.run(inspect())
        assert sent is not None and sent.status == "delivered"
        assert len(events) == 1
        assert events[0].payload_sha256 == hashlib.sha256(delivered_body).hexdigest()
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())


def test_late_delivery_event_does_not_clear_hard_bounce_or_requeue_mail(tmp_path, monkeypatch):
    engine, sessions, seeded = asyncio.run(_database(tmp_path))
    client = _client(monkeypatch, sessions)
    try:
        bounce_body = _payload("email.bounced", extra={"bounce": {"type": "Permanent", "subType": "MailboxUnavailable"}})
        bounce = _post(client, bounce_body, "evt-terminal-bounce-0001")
        late_delivery = _post(client, _payload("email.delivered"), "evt-late-delivery-0001")
        assert bounce.status_code == 200, bounce.text
        assert late_delivery.status_code == 200, late_delivery.text

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
        assert lead.unsubscribed_at is None
        assert sent is not None and sent.status == "bounced"
        assert pending is not None and pending.status == "suppressed"
        assert len(events) == 2
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())
