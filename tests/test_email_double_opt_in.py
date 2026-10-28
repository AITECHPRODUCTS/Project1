from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import EmailConsentConfirmation, Lead, LeadConsentEvent, ScheduledEmail, Workspace
from backend.services import email_delivery
from backend.services.consent_ledger import (
    EMAIL_MARKETING_CONSENT_PURPOSE,
    EMAIL_MARKETING_CONSENT_TEXT,
    EMAIL_MARKETING_CONSENT_VERSION,
)
from backend.tenancy import workspace_scope

WORKSPACE_ID = "double-opt-in-workspace"


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        session.add(Workspace(id=WORKSPACE_ID, name="Double opt-in", slug="double-opt-in"))
        await session.commit()
    return engine, sessions


@pytest.mark.asyncio
async def test_double_opt_in_sends_confirmation_but_queues_no_marketing_until_confirmed(monkeypatch):
    engine, sessions = await _db()
    calls = []
    async def fake_send(url, **kwargs):
        calls.append((url, kwargs))
        return {"id": "resend-confirmation-1"}
    settings = email_delivery.get_settings()
    monkeypatch.setattr(settings, "email_double_opt_in_required", True)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-api-key")
    monkeypatch.setattr(settings, "resend_from_email", "mailer@example.invalid")
    monkeypatch.setattr(settings, "app_public_url", "https://app.example.invalid")
    monkeypatch.setattr(email_delivery, "request_public_json", fake_send)
    try:
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                requested = await email_delivery.capture_lead_and_schedule(
                    session, email_address="reader@example.invalid", consent=True,
                    lead_magnet="A helpful guide", audience="independent creators",
                    offer={"name": "Example offer"}, consent_source="persisted_landing_page",
                    consent_text=EMAIL_MARKETING_CONSENT_TEXT, consent_version=EMAIL_MARKETING_CONSENT_VERSION,
                    consent_purpose=EMAIL_MARKETING_CONSENT_PURPOSE, workspace_id=WORKSPACE_ID,
                )
        assert requested["status"] == "confirmation_pending"
        assert requested["emails_scheduled"] == 0 and requested["confirmation_email_sent"] is True
        assert len(calls) == 1 and calls[0][0] == "https://api.resend.com/emails"
        assert calls[0][1]["headers"]["Idempotency-Key"].startswith("email-consent-confirmation/")
        confirmation_url = calls[0][1]["json_body"]["text"].splitlines()[-1]
        token = confirmation_url.split("token=", 1)[1]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                lead = await session.scalar(select(Lead).where(Lead.email == "reader@example.invalid"))
                confirmations = list((await session.scalars(select(EmailConsentConfirmation))).all())
                queued = list((await session.scalars(select(ScheduledEmail))).all())
                events = list((await session.scalars(select(LeadConsentEvent))).all())
        assert lead is not None and lead.email_consent_confirmed_at is None
        assert len(confirmations) == 1 and confirmations[0].status == "sent"
        assert confirmations[0].token_hash == token_hash and token not in confirmations[0].token_hash
        assert queued == []
        assert len(events) == 1 and events[0].event_type == "consent_confirmation_requested"
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                confirmed = await email_delivery.confirm_email_consent(session, token)
        assert confirmed["status"] == "confirmed" and confirmed["emails_scheduled"] > 0
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                lead = await session.scalar(select(Lead).where(Lead.email == "reader@example.invalid"))
                confirmations = list((await session.scalars(select(EmailConsentConfirmation))).all())
                queued = list((await session.scalars(select(ScheduledEmail))).all())
                events = list((await session.scalars(select(LeadConsentEvent))).all())
        assert lead is not None and lead.email_consent_confirmed_at is not None
        assert len(confirmations) == 1 and confirmations[0].status == "confirmed" and queued
        assert {event.event_type for event in events} == {"consent_confirmation_requested", "consent_confirmed"}
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                with pytest.raises(ValueError, match="already used"):
                    await email_delivery.confirm_email_consent(session, token)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_provider_failure_never_queues_marketing_and_expired_token_is_invalidated(monkeypatch):
    engine, sessions = await _db()
    settings = email_delivery.get_settings()
    monkeypatch.setattr(settings, "email_double_opt_in_required", True)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-api-key")
    monkeypatch.setattr(settings, "resend_from_email", "mailer@example.invalid")
    monkeypatch.setattr(email_delivery, "request_public_json", AsyncMock(side_effect=RuntimeError("provider unavailable")))
    try:
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                failed = await email_delivery.capture_lead_and_schedule(
                    session, email_address="expiry@example.invalid", consent=True,
                    lead_magnet="A helpful guide", audience="independent creators", offer={},
                    workspace_id=WORKSPACE_ID,
                )
        assert failed["status"] == "confirmation_delivery_failed" and failed["emails_scheduled"] == 0
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                confirmation = await session.scalar(select(EmailConsentConfirmation))
                confirmation.status = "sent"
                confirmation.sent_at = datetime.now(timezone.utc)
                token = "a" * 43
                confirmation.token_hash = hashlib.sha256(token.encode()).hexdigest()
                confirmation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await session.commit()
                with pytest.raises(ValueError, match="expired"):
                    await email_delivery.confirm_email_consent(session, token)
                saved = await session.get(EmailConsentConfirmation, confirmation.id)
                queued = list((await session.scalars(select(ScheduledEmail))).all())
                assert saved is not None and saved.status == "expired" and queued == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_double_opt_in_requires_provider_before_mutating_a_lead(monkeypatch):
    engine, sessions = await _db()
    settings = email_delivery.get_settings()
    monkeypatch.setattr(settings, "email_double_opt_in_required", True)
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "resend_from_email", "")
    try:
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                with pytest.raises(email_delivery.ConsentConfirmationDeliveryUnavailable):
                    await email_delivery.capture_lead_and_schedule(
                        session, email_address="not-mutated@example.invalid", consent=True,
                        lead_magnet="A helpful guide", audience="independent creators", offer={},
                        workspace_id=WORKSPACE_ID,
                    )
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                lead = await session.scalar(select(Lead).where(Lead.email == "not-mutated@example.invalid"))
                assert lead is None
    finally:
        await engine.dispose()
