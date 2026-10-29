from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base, get_session
from backend.models import Lead, LeadConsentEvent, ScheduledEmail, Workspace
from backend.schemas import LeadCaptureRequest
from backend.services import email_delivery
from backend.services.consent_ledger import (
    EMAIL_MARKETING_CONSENT_PURPOSE,
    EMAIL_MARKETING_CONSENT_TEXT,
    EMAIL_MARKETING_CONSENT_VERSION,
)
from backend.services.s4_s5_landing import render_workspace_landing_page
from backend.tenancy import workspace_scope


WORKSPACE_ID = "consent-ledger-workspace"


async def _db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        session.add(Workspace(id=WORKSPACE_ID, name="Consent ledger", slug="consent-ledger"))
        await session.commit()
    return engine, sessions


def _override_session(session):
    async def override_get_session():
        yield session
    return override_get_session


def test_landing_page_displays_and_submits_the_exact_versioned_consent_copy():
    html = render_workspace_landing_page(
        headline="A helpful guide",
        subheadline="Useful information for independent creators.",
        benefit_bullets=["A clear first step"],
        privacy_url="https://example.invalid/privacy",
        workspace_token="opaque.signed-token",
    )
    assert f"<span>{EMAIL_MARKETING_CONSENT_TEXT}</span>" in html
    assert f'name="consent_text" value="{EMAIL_MARKETING_CONSENT_TEXT}"' in html
    assert f'name="consent_version" value="{EMAIL_MARKETING_CONSENT_VERSION}"' in html
    assert f'name="consent_purpose" value="{EMAIL_MARKETING_CONSENT_PURPOSE}"' in html
    assert 'name="consent" value="yes" required' in html


def test_consent_api_schema_rejects_client_substituted_copy_or_version():
    base = {
        "email": "reader@example.invalid",
        "consent": True,
        "lead_magnet": "A helpful guide",
        "audience": "independent creators",
    }
    with pytest.raises(ValidationError, match="currently approved text"):
        LeadCaptureRequest.model_validate({**base, "consent_text": "I agree to other things."})
    with pytest.raises(ValidationError, match="not current"):
        LeadCaptureRequest.model_validate({**base, "consent_version": "old-unreviewed-version"})


@pytest.mark.asyncio
async def test_capture_persists_immutable_canonical_consent_evidence_in_same_flow():
    engine, sessions = await _db()
    try:
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                result = await email_delivery.capture_lead_and_schedule(
                    session,
                    email_address="reader@example.invalid",
                    consent=True,
                    lead_magnet="A helpful guide",
                    audience="independent creators",
                    offer={},
                    consent_source="persisted_landing_page",
                    consent_text=EMAIL_MARKETING_CONSENT_TEXT,
                    consent_version=EMAIL_MARKETING_CONSENT_VERSION,
                    consent_purpose=EMAIL_MARKETING_CONSENT_PURPOSE,
                    workspace_id=WORKSPACE_ID,
                )
        lead_id = result["lead_id"]
        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                events = list((await session.scalars(select(LeadConsentEvent).where(
                    LeadConsentEvent.workspace_id == WORKSPACE_ID,
                    LeadConsentEvent.lead_id == lead_id,
                ))).all())
                queued = list((await session.scalars(select(ScheduledEmail).where(
                    ScheduledEmail.workspace_id == WORKSPACE_ID,
                    ScheduledEmail.lead_id == lead_id,
                ))).all())
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "consent_granted"
        assert event.purpose == EMAIL_MARKETING_CONSENT_PURPOSE
        assert event.consent_text == EMAIL_MARKETING_CONSENT_TEXT
        assert event.policy_version == EMAIL_MARKETING_CONSENT_VERSION
        assert event.source == "persisted_landing_page"
        assert event.channel == "email"
        assert event.metadata_json["explicit_checkbox_consent"] is True
        assert event.observed_at is not None
        assert queued, "a consent event should be committed alongside the existing email queue flow"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unsubscribe_appends_once_and_retains_suppression_behavior():
    engine, sessions = await _db()
    try:
        async with sessions() as session:
            lead = Lead(
                workspace_id=WORKSPACE_ID,
                email="reader@example.invalid",
                consent_at=datetime.now(timezone.utc),
                consent_source="persisted_landing_page",
                lead_magnet="A helpful guide",
            )
            session.add(lead)
            await session.flush()
            due = ScheduledEmail(
                workspace_id=WORKSPACE_ID,
                lead_id=lead.id,
                sequence_day=0,
                subject="Welcome",
                body_html="<p>Welcome</p>",
                body_text="Welcome",
                condition_json={"requires_consent": True},
                send_at=datetime.now(timezone.utc),
                status="scheduled",
            )
            session.add(due)
            await session.commit()
            lead_id = lead.id

        async with sessions() as session:
            assert await email_delivery.unsubscribe_lead(session, lead_id) is True
        async with sessions() as session:
            assert await email_delivery.unsubscribe_lead(session, lead_id) is True

        with workspace_scope(WORKSPACE_ID):
            async with sessions() as session:
                events = list((await session.scalars(select(LeadConsentEvent).where(
                    LeadConsentEvent.workspace_id == WORKSPACE_ID,
                    LeadConsentEvent.lead_id == lead_id,
                    LeadConsentEvent.event_type == "unsubscribed",
                ))).all())
                saved_lead = await session.scalar(select(Lead).where(Lead.id == lead_id))
                saved_email = await session.scalar(select(ScheduledEmail).where(ScheduledEmail.id == due.id))
        assert len(events) == 1
        assert events[0].consent_text is None
        assert events[0].source == "signed_unsubscribe_link"
        assert saved_lead is not None and saved_lead.unsubscribed_at is not None
        assert saved_email is not None and saved_email.status == "suppressed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_consent_ledger_cannot_be_mutated_or_deleted_via_orm():
    engine, sessions = await _db()
    try:
        async with sessions() as session:
            event = LeadConsentEvent(
                workspace_id=WORKSPACE_ID,
                lead_id="lead-pseudonymous-id",
                event_type="consent_granted",
                purpose=EMAIL_MARKETING_CONSENT_PURPOSE,
                consent_text=EMAIL_MARKETING_CONSENT_TEXT,
                policy_version=EMAIL_MARKETING_CONSENT_VERSION,
                source="test_form",
                channel="email",
                metadata_json={},
            )
            session.add(event)
            await session.commit()
            event_id = event.id
            event.event_type = "tampered"
            with pytest.raises(ValueError, match="append-only"):
                await session.commit()
            await session.rollback()
            with pytest.raises(ValueError, match="append-only"):
                await session.delete(event)
                await session.commit()
            await session.rollback()
            stored = await session.get(LeadConsentEvent, event_id)
            assert stored is not None and stored.event_type == "consent_granted"
    finally:
        await engine.dispose()


def test_consent_history_api_is_workspace_scoped_read_only():
    observed = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id="event-1",
        event_type="consent_granted",
        purpose=EMAIL_MARKETING_CONSENT_PURPOSE,
        consent_text=EMAIL_MARKETING_CONSENT_TEXT,
        policy_version=EMAIL_MARKETING_CONSENT_VERSION,
        source="persisted_landing_page",
        channel="email",
        metadata_json={"explicit_checkbox_consent": True},
        observed_at=observed,
        created_at=observed,
    )
    scalars_result = SimpleNamespace(all=Mock(return_value=[row]))
    session = SimpleNamespace(
        scalar=AsyncMock(return_value="lead-1"),
        scalars=AsyncMock(return_value=scalars_result),
    )
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": "workspace-1", "email": "reader@example.invalid"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/leads/lead-1/consent-events")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["read_only"] is True and body["count"] == 1
        assert body["data"][0]["event_type"] == "consent_granted"
        assert body["data"][0]["policy_version"] == EMAIL_MARKETING_CONSENT_VERSION
        for statement in (session.scalar.await_args.args[0], session.scalars.await_args.args[0]):
            compiled = statement.compile()
            assert "workspace_id" in str(statement)
            assert "workspace-1" in compiled.params.values()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_lead_list_exposes_double_opt_in_timestamp_and_consent_source():
    observed = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id="lead-confirmed",
        email="reader@example.invalid",
        lead_magnet="Creator guide",
        consent_at=observed,
        email_consent_confirmed_at=observed,
        consent_source="persisted_landing_page",
        unsubscribed_at=None,
        purchased_at=None,
        metadata_json={},
        workspace_id="workspace-1",
    )
    scalars_result = SimpleNamespace(all=Mock(return_value=[row]))
    session = SimpleNamespace(scalar=AsyncMock(return_value=1), scalars=AsyncMock(return_value=scalars_result))
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": "workspace-1", "email": "reader@example.invalid"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/leads")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["count"] == 1
        lead = body["data"][0]
        assert lead["email_consent_confirmed_at"] == observed.isoformat()
        assert lead["consent_source"] == "persisted_landing_page"
        statement = session.scalars.await_args.args[0]
        assert "workspace_id" in str(statement)
        assert "workspace-1" in statement.compile().params.values()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_lead_list_paginates_and_counts_only_the_active_workspace():
    observed = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id="lead-page-50",
        email="page-50@example.invalid",
        lead_magnet="Creator guide",
        consent_at=observed,
        email_consent_confirmed_at=None,
        consent_source="persisted_landing_page",
        unsubscribed_at=None,
        purchased_at=None,
        metadata_json={},
        workspace_id="workspace-1",
    )
    scalars_result = SimpleNamespace(all=Mock(return_value=[row]))
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=51),
        scalars=AsyncMock(return_value=scalars_result),
    )
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": "user-1", "workspace_id": "workspace-1", "email": "reader@example.invalid"
    }
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/leads?limit=1&offset=50&search=Creator")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["count"] == 1
        assert body["total_count"] == 51
        assert body["limit"] == 1
        assert body["offset"] == 50
        assert body["data"][0]["id"] == "lead-page-50"

        count_query = session.scalar.await_args.args[0]
        page_query = session.scalars.await_args.args[0]
        for statement in (count_query, page_query):
            assert "workspace_id" in str(statement)
            assert "workspace-1" in statement.compile().params.values()
        assert page_query._limit_clause.value == 1
        assert page_query._offset_clause.value == 50
        assert "%Creator%" in count_query.compile().params.values()
        assert "%Creator%" in page_query.compile().params.values()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
