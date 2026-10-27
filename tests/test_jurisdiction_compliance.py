from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend import main, workflows
from backend.database import Base, get_session
from backend.models import AuditLog, JurisdictionComplianceAssessment, Workspace
from backend.services.jurisdiction_compliance import REQUIRED_RULE_CATEGORIES, assessment_is_current, evidence_coverage, find_current_assessment
from backend.tenancy import workspace_scope


WORKSPACE_ID = "jurisdiction-compliance-workspace"


async def _setup(monkeypatch):
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

    async def platform_admin():
        return {
            "email": "compliance-admin@example.invalid",
            "user_id": "compliance-admin-1",
            "workspace_id": WORKSPACE_ID,
            "workspace_role": "owner",
            "is_admin": True,
        }

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, platform_admin)
    monkeypatch.setattr(main.settings, "publishing_dry_run", False)
    monkeypatch.setattr(main.settings, "cms_publish_execute", True)
    async with sessions() as db:
        db.add(Workspace(id=WORKSPACE_ID, name="Compliance workspace", slug="jurisdiction-compliance-workspace"))
        await db.commit()
    return engine, sessions


def _evidence(activity: str, jurisdictions: list[str] | None = None, *, reviewed_at: datetime | None = None):
    at = (reviewed_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return [
        {
            "jurisdiction_code": jurisdiction,
            "category": category,
            "source_title": "Official rule reference for " + category.replace("_", " "),
            "source_url": "https://authority.example/legal/" + category,
            "rule_summary": "Reviewed current official guidance and recorded its relevance to this activity.",
            "effective_date": None,
            "reviewed_at": at,
            "reviewer_attestation": True,
        }
        for jurisdiction in (jurisdictions or ["US"])
        for category in REQUIRED_RULE_CATEGORIES[activity]
    ]


def _create_and_approve(client: TestClient, *, activity: str, channels: list[str], jurisdictions: list[str], evidence=None):
    created = client.post("/api/compliance/assessments", json={
        "activity": activity,
        "channels": channels,
        "jurisdictions": jurisdictions,
        "rule_evidence": evidence if evidence is not None else _evidence(activity, jurisdictions),
        "operator_notes": "Scope reviewed for the stated channel and jurisdictions.",
    })
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "review_required", created.text
    result = client.post("/api/compliance/assessments/" + created.json()["id"] + "/review", json={
        "decision": "approve",
        "confirm_scope_reviewed": True,
        "reviewer_notes": "Cited source evidence and scope reviewed by workspace compliance reviewer.",
    })
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "approved"
    return result.json()


def test_evidence_coverage_requires_every_category_for_every_jurisdiction_and_current_attestation():
    evidence = _evidence("content_publish", ["US", "GB"])
    result = evidence_coverage("content_publish", ["US", "GB"], evidence)
    assert result["coverage_complete"] is True
    assert result["required_evidence_items"] == 8

    result = evidence_coverage("content_publish", ["US", "GB"], evidence[:-1])
    assert result["coverage_complete"] is False
    assert result["missing_evidence"][0]["jurisdiction_code"] == "GB"

    stale = _evidence("content_publish", ["US"], reviewed_at=datetime.now(timezone.utc) - timedelta(days=400))
    result = evidence_coverage("content_publish", ["US"], stale)
    assert result["coverage_complete"] is False
    assert {item["reason"] for item in result["missing_evidence"]} == {"stale_evidence"}


def test_review_cannot_approve_incomplete_or_stale_evidence(monkeypatch):
    async def run_test():
        engine, _ = await _setup(monkeypatch)
        stale = _evidence("content_publish", ["US"], reviewed_at=datetime.now(timezone.utc) - timedelta(days=400))
        try:
            with TestClient(main.app) as client:
                created = client.post("/api/compliance/assessments", json={
                    "activity": "content_publish", "channels": ["wordpress"], "jurisdictions": ["US"],
                    "rule_evidence": stale,
                })
                assert created.status_code == 201, created.text
                assert created.json()["status"] == "draft"
                review = client.post("/api/compliance/assessments/" + created.json()["id"] + "/review", json={
                    "decision": "approve", "confirm_scope_reviewed": True,
                    "reviewer_notes": "Attempted stale approval.",
                })
                assert review.status_code == 409, review.text
                assert review.json()["detail"]["code"] == "COMPLIANCE_EVIDENCE_INCOMPLETE"
                assert client.get("/api/compliance/assessments").json()["data"][0]["status"] == "draft"
        finally:
            await engine.dispose()
    asyncio.run(run_test())


def test_live_social_publish_is_blocked_until_matching_assessment_is_approved(monkeypatch):
    async def run_test():
        engine, sessions = await _setup(monkeypatch)
        calls = []

        async def fake_publish(platform, post):
            calls.append((platform, post))
            return {"status": "published", "platform": platform, "remote_id": "social-compliance-1"}

        monkeypatch.setattr(main, "social_media_scheduler", fake_publish)
        payload = {
            "platform": "reddit",
            "post": {"subreddit": "test", "title": "Reviewed post", "text": "Useful compliant post body."},
            "confirm_live_publish": True,
            "target_jurisdictions": ["US"],
        }
        try:
            with TestClient(main.app) as client:
                blocked = client.post(
                    "/api/social/publish", json=payload,
                    headers={"Idempotency-Key": "compliance-social-blocked-0001"},
                )
                assert blocked.status_code == 409, blocked.text
                assert blocked.json()["detail"]["code"] == "COMPLIANCE_APPROVAL_REQUIRED"
                assert calls == []

                _create_and_approve(client, activity="content_publish", channels=["reddit"], jurisdictions=["US"])
                sent = client.post(
                    "/api/social/publish", json=payload,
                    headers={"Idempotency-Key": "compliance-social-approved-0002"},
                )
                assert sent.status_code == 200, sent.text
                assert sent.json()["remote_id"] == "social-compliance-1"
                assert calls == [("reddit", payload["post"])]

            async with sessions() as db:
                events = list((await db.scalars(select(AuditLog).where(
                    AuditLog.workspace_id == WORKSPACE_ID,
                    AuditLog.action == "compliance.live_action.blocked",
                ))).all())
            assert len(events) == 1
            assert events[0].details_json["provider_action_executed"] is False
        finally:
            await engine.dispose()
    asyncio.run(run_test())


def test_live_cms_publish_is_gated_but_draft_mode_remains_available(monkeypatch):
    async def run_test():
        engine, _ = await _setup(monkeypatch)
        calls = []

        async def fake_cms(**kwargs):
            calls.append(kwargs)
            return {"status": kwargs["status"], "provider": kwargs["provider"], "remote_id": "cms-compliance-1"}

        monkeypatch.setattr(main, "publish_article", fake_cms)
        payload = {
            "provider": "wordpress",
            "title": "Reviewed affiliate article",
            "article_html": "<html><body><p>This is an adequately sized reviewed article.</p></body></html>",
            "canonical_url": "https://publisher.example/article",
            "status": "publish",
            "confirm_live_publish": True,
            "target_jurisdictions": ["US"],
        }
        try:
            with TestClient(main.app) as client:
                draft = client.post("/api/cms/publish", json={
                    **payload, "status": "draft", "confirm_live_publish": False, "target_jurisdictions": []
                }, headers={"Idempotency-Key": "compliance-cms-draft-0001"})
                assert draft.status_code == 200, draft.text
                blocked = client.post(
                    "/api/cms/publish", json=payload,
                    headers={"Idempotency-Key": "compliance-cms-blocked-0002"},
                )
                assert blocked.status_code == 409, blocked.text
                assert blocked.json()["detail"]["code"] == "COMPLIANCE_APPROVAL_REQUIRED"
                assert len(calls) == 1 and calls[0]["status"] == "draft"

                _create_and_approve(client, activity="content_publish", channels=["wordpress"], jurisdictions=["US"])
                published = client.post(
                    "/api/cms/publish", json=payload,
                    headers={"Idempotency-Key": "compliance-cms-approved-0003"},
                )
                assert published.status_code == 200, published.text
                assert published.json()["remote_id"] == "cms-compliance-1"
                assert [item["status"] for item in calls] == ["draft", "publish"]
        finally:
            await engine.dispose()
    asyncio.run(run_test())


def test_current_assessment_does_not_cross_channel_or_jurisdiction_boundaries(monkeypatch):
    async def run_test():
        engine, sessions = await _setup(monkeypatch)
        try:
            with TestClient(main.app) as client:
                assessment = _create_and_approve(
                    client, activity="content_publish", channels=["wordpress"], jurisdictions=["US"]
                )
            async with sessions() as db:
                assert await find_current_assessment(
                    db, workspace_id=WORKSPACE_ID, activity="content_publish", jurisdictions=["US"], channel="wordpress"
                ) is not None
                assert await find_current_assessment(
                    db, workspace_id=WORKSPACE_ID, activity="content_publish", jurisdictions=["US"], channel="reddit"
                ) is None
                assert await find_current_assessment(
                    db, workspace_id=WORKSPACE_ID, activity="content_publish", jurisdictions=["GB"], channel="wordpress"
                ) is None
            now = datetime.now(timezone.utc)
            row = JurisdictionComplianceAssessment(
                id=assessment["id"], workspace_id=WORKSPACE_ID, activity="content_publish",
                channels_json=["wordpress"], jurisdictions_json=["US"],
                rule_evidence_json=assessment["rule_evidence"], status="approved", created_by="creator",
                reviewed_by="reviewer", reviewed_at=datetime.fromisoformat(assessment["reviewed_at"]),
                valid_until=datetime.fromisoformat(assessment["valid_until"]),
            )
            ok, _ = assessment_is_current(row, activity="content_publish", jurisdictions=["US"], channel="wordpress", now=now)
            assert ok is True
        finally:
            await engine.dispose()
    asyncio.run(run_test())


def test_workflow_live_distribution_blocks_without_scope_and_proceeds_with_current_approval(monkeypatch):
    async def run_test():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(workflows, "SessionLocal", sessions)
        monkeypatch.setattr(workflows, "get_settings", lambda: type("Settings", (), {"publishing_dry_run": False})())
        async with sessions() as db:
            db.add(Workspace(id=WORKSPACE_ID, name="Compliance workflow", slug="compliance-workflow"))
            await db.commit()
        calls = []

        async def fake_publish(platform, post):
            calls.append((platform, post))
            return {"status": "published", "platform": platform, "remote_id": "workflow-compliance-1"}

        monkeypatch.setattr(workflows, "social_media_scheduler", fake_publish)
        state = {
            "publish_requests": [{"platform": "reddit", "post": {"subreddit": "test", "title": "title", "text": "body"}}],
            "metadata": {
                "workspace_id": WORKSPACE_ID, "platform_admin_authorized": True, "live_publish_confirmed": True,
                "workflow_publish_idempotency_key": "workflow-compliance-key-0001", "target_jurisdictions": ["US"],
            },
        }
        try:
            with workspace_scope(WORKSPACE_ID):
                with pytest.raises(PermissionError, match="compliance assessment"):
                    await workflows.s5(state)
            assert calls == []

            now = datetime.now(timezone.utc)
            evidence = _evidence("content_publish", ["US"])
            coverage = evidence_coverage("content_publish", ["US"], evidence, now=now)
            async with sessions() as db:
                db.add(JurisdictionComplianceAssessment(
                    workspace_id=WORKSPACE_ID, activity="content_publish", channels_json=["reddit"],
                    jurisdictions_json=["US"], rule_evidence_json=evidence, coverage_summary_json=coverage,
                    status="approved", created_by="owner@example.invalid", reviewed_by="reviewer@example.invalid",
                    reviewed_at=now, valid_until=now + timedelta(days=180),
                ))
                await db.commit()
            state["metadata"]["workflow_publish_idempotency_key"] = "workflow-compliance-key-0002"
            with workspace_scope(WORKSPACE_ID):
                result = await workflows.s5(state)
            assert result["s5_result"]["publish_results"][0]["remote_id"] == "workflow-compliance-1"
            assert calls == [("reddit", state["publish_requests"][0]["post"])]
        finally:
            await engine.dispose()
    asyncio.run(run_test())
