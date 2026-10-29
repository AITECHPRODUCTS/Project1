from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend import main
from backend.database import Base, get_session
from backend.models import (
    AuditLog, EmailDeliveryEvent, Lead, LeadConsentEvent, ScheduledEmail, Workspace,
)
from backend.tenancy import workspace_scope


OBSERVED_AT = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


def test_lead_json_data_export_is_scoped_audited_bounded_and_content_minimized(tmp_path, monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///" + str(tmp_path / "lead-data-export.sqlite3"),
        poolclass=NullPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace_a = Workspace(name="Data export A", slug="data-export-a")
            workspace_b = Workspace(name="Data export B", slug="data-export-b")
            db.add_all([workspace_a, workspace_b])
            await db.flush()
            with workspace_scope(workspace_a.id):
                lead_a = Lead(
                    workspace_id=workspace_a.id,
                    email="reader@example.test",
                    consent_at=OBSERVED_AT,
                    email_consent_confirmed_at=OBSERVED_AT,
                    consent_source="persisted_landing_page",
                    lead_magnet="Creator guide",
                    metadata_json={"attribution": {"first_touch": {"utm_source": "newsletter"}}},
                )
                db.add(lead_a)
                await db.flush()
                db.add_all([
                    LeadConsentEvent(
                        workspace_id=workspace_a.id,
                        lead_id=lead_a.id,
                        event_type="consent_granted",
                        purpose="email_marketing",
                        consent_text="I agree to receive this resource and related emails.",
                        policy_version="email-marketing-v1",
                        source="persisted_landing_page",
                        channel="email",
                        metadata_json={"explicit_checkbox_consent": True},
                        observed_at=OBSERVED_AT,
                    ),
                    EmailDeliveryEvent(
                        workspace_id=workspace_a.id,
                        lead_id=lead_a.id,
                        provider="resend",
                        provider_event_id="evt-data-export-0001",
                        provider_message_id="re_msg_data_export_0001",
                        event_type="email.bounced",
                        outcome="bounced",
                        event_created_at=OBSERVED_AT,
                        payload_sha256="b" * 64,
                        metadata_json={
                            "recipient_count": 1,
                            "bounce_type": "permanent",
                            "bounce_subtype": "mailbox_unavailable",
                        },
                        received_at=OBSERVED_AT,
                    ),
                    ScheduledEmail(
                        workspace_id=workspace_a.id,
                        lead_id=lead_a.id,
                        sequence_day=1,
                        subject="Private template subject",
                        body_html="<p>Private template body</p>",
                        body_text="Private template body",
                        condition_json={"requires_consent": True},
                        send_at=OBSERVED_AT,
                        status="suppressed",
                        attempts=1,
                    ),
                ])
                # Flush workspace-A rows while workspace A is active. Otherwise
                # SQLAlchemy may defer these writes until workspace B is active,
                # correctly triggering the cross-workspace write guard.
                await db.flush()
            with workspace_scope(workspace_b.id):
                lead_b = Lead(
                    workspace_id=workspace_b.id,
                    email="other-reader@example.test",
                    consent_at=OBSERVED_AT,
                    consent_source="persisted_landing_page",
                    lead_magnet="Other guide",
                    metadata_json={},
                )
                db.add(lead_b)
                await db.flush()
                db.add(LeadConsentEvent(
                    workspace_id=workspace_b.id,
                    lead_id=lead_b.id,
                    event_type="consent_granted",
                    purpose="email_marketing",
                    consent_text="Other tenant consent text",
                    policy_version="email-marketing-v1",
                    source="persisted_landing_page",
                    channel="email",
                    metadata_json={},
                    observed_at=OBSERVED_AT,
                ))
            await db.commit()
            return workspace_a.id, workspace_b.id, lead_a.id, lead_b.id

    workspace_a, workspace_b, lead_a, lead_b = asyncio.run(seed())

    async def override_get_session():
        async with sessions() as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_get_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, lambda: {
        "user_id": "owner-a",
        "workspace_id": workspace_a,
        "workspace_role": "owner",
        "email": "exporter@example.test",
    })
    client = TestClient(main.app)
    try:
        response = client.get(f"/api/leads/{lead_a}/data-export.json")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["cache-control"] == "no-store, private"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"].endswith(".json\"")
        package = response.json()
        assert package["format"] == "omni-affiliate-lead-data"
        assert package["format_version"] == "1.0"
        assert package["lead"]["email"] == "reader@example.test"
        assert package["consent_events"][0]["consent_text"].startswith("I agree")
        assert package["email_delivery_events"][0]["outcome"] == "bounced"
        assert package["scheduled_email_activity"][0]["status"] == "suppressed"
        assert "Private template body" not in response.text
        assert "Private template subject" not in response.text
        assert "payload_sha256" not in response.text
        assert "other-reader@example.test" not in response.text
        assert "Other tenant consent text" not in response.text

        cross_workspace = client.get(f"/api/leads/{lead_b}/data-export.json")
        assert cross_workspace.status_code == 404

        monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, lambda: {
            "user_id": "owner-a", "workspace_id": None, "email": "exporter@example.test",
        })
        no_workspace = client.get(f"/api/leads/{lead_a}/data-export.json")
        assert no_workspace.status_code == 403

        monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, lambda: {
            "user_id": "owner-a", "workspace_id": workspace_a, "email": "exporter@example.test",
        })
        monkeypatch.setattr(main, "MAX_LEAD_DATA_EXPORT_ITEMS", 0)
        rejected = client.get(f"/api/leads/{lead_a}/data-export.json")
        assert rejected.status_code == 413
        assert "no partial export" in rejected.json()["detail"].lower()

        async def audit_rows():
            async with sessions() as db:
                with workspace_scope(workspace_a):
                    rows = list((await db.scalars(select(AuditLog).where(
                        AuditLog.workspace_id == workspace_a,
                        AuditLog.action == "leads.export_data_json",
                    ).order_by(AuditLog.created_at.asc()))).all())
                other_rows = list((await db.scalars(select(AuditLog).where(
                    AuditLog.workspace_id == workspace_b,
                    AuditLog.action == "leads.export_data_json",
                ))).all())
                return rows, other_rows

        rows, other_rows = asyncio.run(audit_rows())
        assert len(rows) == 2
        assert [row.outcome for row in rows] == ["completed", "rejected_row_limit"]
        assert rows[0].details_json["lead_email_recorded"] is False
        assert rows[0].details_json["export_values_recorded"] is False
        assert rows[0].resource_id != lead_a
        assert other_rows == []
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())
