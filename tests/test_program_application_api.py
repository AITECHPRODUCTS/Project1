from __future__ import annotations

import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import Workspace


def packet(*, complete: bool = False):
    return {
        "provider": "Example Affiliate Network",
        "program_name": "Example Publisher Program",
        "program_url": "https://example.com/affiliate-terms",
        "publisher_website_url": "https://publisher.example.com",
        "audience_description": "An audience of readers looking for carefully sourced marketing education and software comparisons.",
        "monthly_visitors": 12000,
        "traffic_sources": ["seo", "blog", "email_opt_in"],
        "promotion_channels": ["website", "blog", "newsletter", "comparison_content"],
        "primary_regions": ["US", "GB"],
        "promotion_plan": "We will publish evidence-based educational articles and clearly labeled comparisons for the selected audience. Affiliate links will be disclosed, paid traffic will only be used where program terms permit it, and unsupported product claims will be omitted.",
        "evidence_urls": ["https://example.com/affiliate-terms"] if complete else [],
        "compliance_answers": {
            "affiliate_disclosure_ready": complete,
            "program_traffic_terms_reviewed": complete,
            "geography_restrictions_reviewed": complete,
            "privacy_and_consent_controls_ready": complete,
            "claims_substantiation_process_ready": complete,
        },
    }


def make_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'program-applications.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace = Workspace(name="Program Application Workspace", slug="program-application-test")
            db.add(workspace)
            await db.flush()
            workspace_id = workspace.id
            await db.commit()
        return workspace_id

    workspace_id = asyncio.run(setup())
    user = {"workspace_id": workspace_id, "workspace_role": "owner",
            "email": "owner@example.com", "is_admin": False}

    async def override_session():
        async with sessions() as db:
            yield db

    async def override_auth():
        return user

    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, user, TestClient(main.app)


def test_application_packet_is_persisted_but_not_submitted(tmp_path):
    engine, user, client = make_client(tmp_path)
    try:
        with client:
            response = client.post("/api/research/program-applications", json=packet())
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["status"] == "draft"
            assert body["readiness"]["ready_for_human_review"] is False
            assert "official_program_terms_evidence_required" in body["readiness"]["blockers"]
            assert body["provider_submission_status"] == "not_configured"
            assert body["provider_submission_performed"] is False
            listed = client.get("/api/research/program-applications")
            assert listed.status_code == 200
            assert listed.json()["count"] == 1
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        client.close()
        asyncio.run(engine.dispose())


def test_manual_handoff_requires_evidence_and_all_compliance_checks(tmp_path):
    engine, user, client = make_client(tmp_path)
    try:
        with client:
            incomplete = client.post("/api/research/program-applications", json=packet()).json()
            blocked = client.post(
                f"/api/research/program-applications/{incomplete['id']}/review",
                json={"decision": "approve_for_manual_handoff", "reviewer_notes": "Review terms first"},
            )
            assert blocked.status_code == 409, blocked.text

            ready = client.post("/api/research/program-applications", json=packet(complete=True))
            assert ready.status_code == 201, ready.text
            application = ready.json()
            approved = client.post(
                f"/api/research/program-applications/{application['id']}/review",
                json={"decision": "approve_for_manual_handoff", "reviewer_notes": "Ready for operator handoff"},
            )
            assert approved.status_code == 200, approved.text
            result = approved.json()
            assert result["status"] == "approved_for_manual_handoff"
            assert result["provider_submission_status"] == "not_configured"
            assert result["provider_submission_performed"] is False
            assert result["provider_approved"] is False
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        client.close()
        asyncio.run(engine.dispose())


def test_non_admin_workspace_member_cannot_review_application(tmp_path):
    engine, user, client = make_client(tmp_path)
    try:
        with client:
            ready = client.post("/api/research/program-applications", json=packet(complete=True)).json()
            user["workspace_role"] = "member"
            response = client.post(
                f"/api/research/program-applications/{ready['id']}/review",
                json={"decision": "approve_for_manual_handoff"},
            )
            assert response.status_code == 403, response.text
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        client.close()
        asyncio.run(engine.dispose())
