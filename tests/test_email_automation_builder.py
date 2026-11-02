from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main
from backend.database import Base
from backend.models import AuditLog, ContentAsset, Workspace
from backend.services.email_automation_builder import build_email_automation, simulate_email_automation


def graph_payload(**overrides):
    data = {
        "name": "Creator nurture",
        "description": "A useful opt-in email journey with purchase and engagement branches.",
        "version": "1.0.0",
        "entry_step_id": "welcome",
        "target_jurisdictions": ["US"],
        "nodes": [
            {"id": "welcome", "kind": "email", "subject": "Your guide is ready",
             "body_text": "Thanks for requesting the guide. Start with one practical step.",
             "delay_days": 0, "next_step_id": "purchase-check"},
            {"id": "purchase-check", "kind": "branch", "condition": "purchased",
             "true_step_id": "purchased-stop", "false_step_id": "engagement-check"},
            {"id": "engagement-check", "kind": "branch", "condition": "engaged",
             "true_step_id": "engaged-followup", "false_step_id": "quiet-followup"},
            {"id": "engaged-followup", "kind": "email", "subject": "A practical next step",
             "body_text": "Apply the guide to one small task and evaluate the result.",
             "delay_days": 2, "next_step_id": "done"},
            {"id": "quiet-followup", "kind": "email", "subject": "A simple checklist",
             "body_text": "Use this short checklist to compare your next steps.",
             "delay_days": 3, "next_step_id": "done"},
            {"id": "purchased-stop", "kind": "stop"},
            {"id": "done", "kind": "stop"},
        ],
    }
    data.update(overrides)
    return data


def test_builder_checksums_stable_and_graph_counts_are_transparent():
    first = build_email_automation(graph_payload())
    second = build_email_automation(graph_payload())
    assert first["sha256"] == second["sha256"]
    assert len(first["sha256"]) == 64
    assert first["validation_report"]["node_count"] == 7
    assert first["validation_report"]["email_step_count"] == 3
    assert first["validation_report"]["branch_count"] == 2
    assert first["validation_report"]["provider_calls_made"] == 0


@pytest.mark.parametrize(
    ("context", "expected_path", "expected_subject"),
    [
        ({"purchased": True, "engaged": True}, ["welcome", "purchase-check:true", "purchased-stop"], None),
        ({"purchased": False, "engaged": True}, ["welcome", "purchase-check:false", "engagement-check:true", "engaged-followup", "done"], "A practical next step"),
        ({"purchased": False, "engaged": False}, ["welcome", "purchase-check:false", "engagement-check:false", "quiet-followup", "done"], "A simple checklist"),
    ],
)
def test_simulation_selects_expected_branch_without_delivery(context, expected_path, expected_subject):
    result = simulate_email_automation(graph_payload(), **context)
    assert result["path"] == expected_path
    assert result["provider_calls_made"] == 0
    assert result["messages_scheduled"] == 0
    assert result["messages_sent"] == 0 if "messages_sent" in result else True
    if expected_subject is None:
        assert len(result["emails"]) == 1
    else:
        assert result["emails"][-1]["subject"] == expected_subject


@pytest.mark.parametrize(
    ("consent_granted", "unsubscribed", "reason"),
    [(False, False, "consent_not_granted"), (True, True, "recipient_unsubscribed")],
)
def test_simulation_short_circuits_without_consent_or_after_unsubscribe(consent_granted, unsubscribed, reason):
    result = simulate_email_automation(
        graph_payload(), consent_granted=consent_granted, unsubscribed=unsubscribed
    )
    assert result["path"] == []
    assert result["emails"] == []
    assert result["stop_reason"] == reason
    assert result["provider_calls_made"] == 0


def test_validator_rejects_cycles_unknown_targets_and_missing_affiliate_disclosure():
    cyclic = graph_payload()
    cyclic["nodes"][0]["next_step_id"] = "welcome"
    with pytest.raises(ValueError, match="cycle"):
        build_email_automation(cyclic)

    missing_target = graph_payload()
    missing_target["nodes"][0]["next_step_id"] = "missing"
    with pytest.raises(ValueError, match="unknown step"):
        build_email_automation(missing_target)

    missing_disclosure = graph_payload()
    missing_disclosure["nodes"][0]["has_affiliate_links"] = True
    with pytest.raises(ValueError, match="affiliate_disclosure"):
        build_email_automation(missing_disclosure)


def _setup(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    active = {"workspace_id": "email-automation-workspace-a"}

    async def override_session():
        async with sessions() as session:
            yield session

    async def workspace_admin():
        return {
            "email": "automation-admin@example.invalid",
            "user_id": "automation-admin",
            "workspace_id": active["workspace_id"],
            "workspace_role": "owner",
            "is_admin": True,
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, workspace_admin)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_admin, workspace_admin)

    async def create_rows():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add_all([
                Workspace(id="email-automation-workspace-a", name="Automation A", slug="email-automation-a"),
                Workspace(id="email-automation-workspace-b", name="Automation B", slug="email-automation-b"),
            ])
            await db.commit()

    asyncio.run(create_rows())
    return engine, sessions, active


def test_api_persists_automation_reviews_simulates_and_keeps_workspace_isolation(monkeypatch):
    engine, sessions, active = _setup(monkeypatch)
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/email/automations", json=graph_payload())
            assert created.status_code == 201, created.text
            body = created.json()
            automation_id = body["id"]
            assert body["status"] == "review_required"
            assert body["graph_sha256"] == body["validation_report"]["checksum_sha256"]
            assert "no email is queued or sent" in body["execution_boundary"]

            duplicate = client.post("/api/email/automations", json=graph_payload())
            assert duplicate.status_code == 409

            simulation = client.post(f"/api/email/automations/{automation_id}/simulate", json={
                "purchased": False, "engaged": True, "consent_granted": True, "unsubscribed": False,
            })
            assert simulation.status_code == 200, simulation.text
            assert simulation.json()["simulation"]["emails"][-1]["subject"] == "A practical next step"
            assert simulation.json()["provider_calls_made"] == 0

            no_confirmation = client.post(f"/api/email/automations/{automation_id}/review", json={
                "decision": "approve", "confirm_graph_reviewed": False,
            })
            assert no_confirmation.status_code == 409

            reviewed = client.post(f"/api/email/automations/{automation_id}/review", json={
                "decision": "approve", "confirm_graph_reviewed": True,
                "reviewer_notes": "Reviewed the opt-in journey and branch logic.",
            })
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["status"] == "approved"
            immutable = client.post(f"/api/email/automations/{automation_id}/review", json={
                "decision": "reject",
            })
            assert immutable.status_code == 409

            active["workspace_id"] = "email-automation-workspace-b"
            other_list = client.get("/api/email/automations")
            hidden = client.get(f"/api/email/automations/{automation_id}")
            assert other_list.status_code == 200 and other_list.json()["count"] == 0
            assert hidden.status_code == 404

        async def rows():
            async with sessions() as db:
                assets = list((await db.scalars(select(ContentAsset).where(
                    ContentAsset.asset_type == "email_automation"
                ))).all())
                audits = list((await db.scalars(select(AuditLog).where(
                    AuditLog.action.in_(["email_automation.created", "email_automation.reviewed"])
                ))).all())
            return assets, audits
        assets, audits = asyncio.run(rows())
        assert len(assets) == 1
        assert assets[0].status == "approved"
        assert len(audits) == 2
        assert all(item.details_json["side_effects_performed"] is False if item.action == "email_automation.created" else item.details_json["runtime_activated"] is False for item in audits)
    finally:
        asyncio.run(engine.dispose())
