from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import AuditLog, ContentAsset, Lead, PlatformExecutionControl, ScheduledEmail, Workspace
from backend.services import email_delivery
from backend.services.email_automation_builder import build_email_automation
from backend.tenancy import workspace_scope


def _simple_graph():
    return build_email_automation({
        "name": "Compliance-gated nurture",
        "description": "A reviewed branching sequence for confirmed email subscribers.",
        "version": "1.0.0",
        "entry_step_id": "welcome",
        "target_jurisdictions": ["US"],
        "nodes": [
            {"id": "welcome", "kind": "email", "subject": "Welcome", "body_text": "Here is the resource you requested.", "delay_days": 0, "next_step_id": "purchase-check"},
            {"id": "purchase-check", "kind": "branch", "condition": "purchased", "true_step_id": "done", "false_step_id": "follow-up"},
            {"id": "follow-up", "kind": "email", "subject": "One useful next step", "body_text": "Try one step from the resource and assess the result.", "delay_days": 2, "next_step_id": "done"},
            {"id": "done", "kind": "stop"},
        ],
    })


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
        session.add(Workspace(id="email-runtime-workspace", name="Email runtime", slug="email-runtime-workspace"))
        session.add(PlatformExecutionControl(id=1, outbound_actions_paused=False))
        await session.commit()
    return engine, sessions


async def _add_approved_graph(sessions):
    built = _simple_graph()
    async with sessions() as session:
        row = ContentAsset(
            workspace_id="email-runtime-workspace",
            asset_type="email_automation",
            title=built["graph"]["name"],
            body=json.dumps(built["graph"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            status="approved",
            source_urls=[],
            metadata_json={
                "name": built["graph"]["name"], "description": built["graph"]["description"],
                "version": built["graph"]["version"], "entry_step_id": built["graph"]["entry_step_id"],
                "target_jurisdictions": built["graph"]["target_jurisdictions"],
                "node_count": len(built["graph"]["nodes"]), "graph_sha256": built["sha256"],
                "validation_report": built["validation_report"], "reviewed_by": "reviewer@example.invalid",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        session.add(row)
        await session.commit()
        return row.id, built


@pytest.mark.asyncio
async def test_capture_approved_automation_queues_only_entry_step_and_supersedes_legacy_queue():
    engine, sessions = await _db()
    try:
        automation_id, built = await _add_approved_graph(sessions)
        async with sessions() as session:
            with workspace_scope("email-runtime-workspace"):
                lead = Lead(
                    workspace_id="email-runtime-workspace", email="subscriber@example.invalid",
                    consent_at=datetime.now(timezone.utc), consent_source="website_form",
                    lead_magnet="A practical guide",
                )
                session.add(lead)
                await session.flush()
                legacy = ScheduledEmail(
                    workspace_id="email-runtime-workspace", lead_id=lead.id, sequence_day=0,
                    subject="Legacy sequence", body_html="<p>Legacy</p>", body_text="Legacy",
                    condition_json={"requires_consent": True}, send_at=datetime.now(timezone.utc),
                    status="scheduled",
                )
                session.add(legacy)
                await session.commit()
                lead_id = lead.id
        with workspace_scope("email-runtime-workspace"):
            async with sessions() as session:
                result = await email_delivery.capture_lead_and_schedule(
                    session, email_address="subscriber@example.invalid", consent=True,
                    lead_magnet="A practical guide", audience="creator tools", offer={},
                    consent_source="website_form", email_automation_id=automation_id,
                    workspace_id="email-runtime-workspace",
                )
        assert result["emails_scheduled"] == 1
        assert result["automation_id"] == automation_id
        async with sessions() as session:
            emails = list((await session.scalars(select(ScheduledEmail).where(
                ScheduledEmail.workspace_id == "email-runtime-workspace", ScheduledEmail.lead_id == lead_id
            ))).all())
        old = next(item for item in emails if item.subject == "Legacy sequence")
        first = next(item for item in emails if item.condition_json.get("automation_id") == automation_id)
        assert old.status == "suppressed"
        assert first.subject == "Welcome"
        assert first.condition_json["automation_step_id"] == "welcome"
        assert first.condition_json["automation_graph_sha256"] == built["sha256"]
        assert first.condition_json["automation_target_jurisdictions"] == ["US"]
        assert "Unsubscribe:" in first.body_text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_automation_delivery_is_deferred_without_current_email_marketing_compliance(monkeypatch):
    engine, sessions = await _db()
    requests = []
    async def forbidden_provider_call(*args, **kwargs):
        requests.append((args, kwargs))
        raise AssertionError("Provider must not be called without current compliance approval")
    monkeypatch.setattr(email_delivery, "request_public_json", forbidden_provider_call)
    settings = email_delivery.get_settings()
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-key")
    monkeypatch.setattr(settings, "resend_from_email", "mailer@example.invalid")
    try:
        automation_id, built = await _add_approved_graph(sessions)
        async with sessions() as session:
            with workspace_scope("email-runtime-workspace"):
                lead = Lead(
                    workspace_id="email-runtime-workspace", email="subscriber@example.invalid",
                    consent_at=datetime.now(timezone.utc), consent_source="website_form",
                    lead_magnet="A practical guide",
                )
                session.add(lead)
                await session.flush()
                due = ScheduledEmail(
                    workspace_id="email-runtime-workspace", lead_id=lead.id, sequence_day=0,
                    subject="Welcome", body_html="<p>Welcome</p>", body_text="Welcome",
                    condition_json={
                        "requires_consent": True, "skip_if_unsubscribed": True,
                        "automation_id": automation_id, "automation_step_id": "welcome",
                        "automation_graph_sha256": built["sha256"],
                        "automation_target_jurisdictions": ["US"],
                    },
                    send_at=datetime.now(timezone.utc) - timedelta(minutes=1), status="scheduled",
                )
                session.add(due)
                await session.commit()
                due_id = due.id
            with workspace_scope("email-runtime-workspace"):
                result = await email_delivery.send_due_emails(
                    session, limit=10, workspace_id="email-runtime-workspace"
                )
        assert requests == []
        assert result["sent"] == 0 and result["skipped"] == 1
        async with sessions() as session:
            due = await session.get(ScheduledEmail, due_id)
        assert due is not None and due.status == "scheduled"
        stored_send_at = due.send_at
        if stored_send_at.tzinfo is None:
            stored_send_at = stored_send_at.replace(tzinfo=timezone.utc)
        assert stored_send_at > datetime.now(timezone.utc)
        assert "compliance assessment required" in (due.last_error or "").lower()
        assert due.attempts == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_next_email_node_is_scheduled_only_after_current_node_is_sent():
    engine, sessions = await _db()
    try:
        automation_id, built = await _add_approved_graph(sessions)
        async with sessions() as session:
            with workspace_scope("email-runtime-workspace"):
                lead = Lead(
                    workspace_id="email-runtime-workspace", email="subscriber@example.invalid",
                    consent_at=datetime.now(timezone.utc), consent_source="website_form",
                    lead_magnet="A practical guide",
                )
                session.add(lead)
                await session.flush()
                sent = ScheduledEmail(
                    workspace_id="email-runtime-workspace", lead_id=lead.id, sequence_day=0,
                    subject="Welcome", body_html="<p>Welcome</p>", body_text="Welcome",
                    condition_json={
                        "automation_id": automation_id, "automation_step_id": "welcome",
                        "automation_graph_sha256": built["sha256"],
                        "automation_target_jurisdictions": ["US"],
                    },
                    send_at=datetime.now(timezone.utc), status="sent",
                )
                session.add(sent)
                await session.flush()
                await email_delivery._queue_next_automation_step(
                    session, workspace_id="email-runtime-workspace", lead=lead,
                    sent_message=sent, now=datetime.now(timezone.utc),
                )
                await session.commit()
                queued = list((await session.scalars(select(ScheduledEmail).where(
                    ScheduledEmail.workspace_id == "email-runtime-workspace",
                    ScheduledEmail.lead_id == lead.id, ScheduledEmail.id != sent.id,
                ))).all())
        assert len(queued) == 1
        assert queued[0].subject == "One useful next step"
        assert queued[0].condition_json["automation_step_id"] == "follow-up"
    finally:
        await engine.dispose()



@pytest.mark.asyncio
async def test_resubscribe_requires_fresh_confirmation_and_starts_a_new_sequence(monkeypatch):
    engine, sessions = await _db()
    async def offline_complete(*args, **kwargs):
        return {"text": "[]", "provider": "offline"}

    monkeypatch.setattr(email_delivery.llm_service, "complete", offline_complete)
    workspace_id = "email-runtime-workspace"
    lead_id = None
    now = datetime.now(timezone.utc)
    try:
        async with sessions() as session:
            with workspace_scope(workspace_id):
                lead = Lead(
                    workspace_id=workspace_id,
                    email="previously-unsubscribed@example.invalid",
                    consent_at=now - timedelta(days=30),
                    consent_source="website_form",
                    lead_magnet="Starter guide",
                    unsubscribed_at=now - timedelta(days=2),
                )
                session.add(lead)
                await session.flush()
                lead_id = lead.id
                for day in range(5):
                    session.add(ScheduledEmail(
                        workspace_id=workspace_id,
                        lead_id=lead.id,
                        sequence_day=day,
                        subject=f"Old sequence {day}",
                        body_text="Old email",
                        body_html="<p>Old email</p>",
                        condition_json={"requires_consent": True, "skip_if_unsubscribed": True},
                        send_at=now + timedelta(days=day),
                        status="suppressed",
                        last_error="Recipient unsubscribed; pending delivery canceled.",
                    ))
                await session.commit()

        async with sessions() as session:
            with workspace_scope(workspace_id):
                with pytest.raises(ValueError, match="explicit resubscribe confirmation"):
                    await email_delivery.capture_lead_and_schedule(
                        session,
                        email_address="previously-unsubscribed@example.invalid",
                        consent=True,
                        lead_magnet="Updated starter guide",
                        audience="independent creators",
                        offer={"name": "Example offer", "url": "https://example.invalid"},
                        consent_source="resubscribe_form",
                        workspace_id=workspace_id,
                    )
                await session.rollback()

        async with sessions() as session:
            with workspace_scope(workspace_id):
                result = await email_delivery.capture_lead_and_schedule(
                    session,
                    email_address="previously-unsubscribed@example.invalid",
                    consent=True,
                    lead_magnet="Updated starter guide",
                    audience="independent creators",
                    offer={"name": "Example offer", "url": "https://example.invalid"},
                    consent_source="resubscribe_form",
                    resubscribe_confirmed=True,
                    workspace_id=workspace_id,
                )
        assert result["emails_scheduled"] == 5
        assert result["sequence_days"] == [5, 6, 7, 8, 9]

        with workspace_scope(workspace_id):
            async with sessions() as session:
                lead = await session.scalar(select(Lead).where(Lead.id == lead_id))
                assert lead is not None
                assert lead.unsubscribed_at is None
                assert lead.consent_source == "resubscribe_form"
                messages = list((await session.scalars(
                    select(ScheduledEmail).where(ScheduledEmail.lead_id == lead_id)
                    .order_by(ScheduledEmail.sequence_day.asc())
                )).all())
                assert [message.sequence_day for message in messages] == list(range(10))
                assert all(message.status == "suppressed" for message in messages[:5])
                assert all(message.status == "scheduled" for message in messages[5:])
                audit = await session.scalar(select(AuditLog).where(
                    AuditLog.workspace_id == workspace_id,
                    AuditLog.resource_id == lead_id,
                    AuditLog.action == "email.consent.resubscribed",
                ))
                assert audit is not None
                assert audit.details_json["explicit_confirmation"] is True
                assert audit.details_json["source"] == "resubscribe_form"
    finally:
        await engine.dispose()
