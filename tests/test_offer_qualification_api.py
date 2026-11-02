from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import Offer, Workspace


def _qualification_app(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'qualification.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            a = Workspace(name="Qualification A", slug="qualification-a")
            b = Workspace(name="Qualification B", slug="qualification-b")
            db.add_all([a, b])
            await db.flush()
            offer = Offer(network="openaffiliate", external_id="qualify-me", name="Qualification candidate",
                description="Candidate with unverified provider terms", verified=True, epc=None, conversion_rate=None)
            db.add(offer)
            await db.commit()
            return a.id, b.id, offer.id
    workspace_a, workspace_b, offer_id = asyncio.run(setup())
    user = {"workspace_id": workspace_a, "workspace_role": "owner", "email": "reviewer@example.com", "user_id": "reviewer", "is_admin": False}
    async def override_session():
        async with sessions() as db:
            yield db
    async def override_auth():
        return user
    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, user, workspace_b, offer_id, TestClient(main.app)


def _cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_qualification_review_requires_checklist_and_evidence_then_persists_workspace_decision(tmp_path):
    engine, user, workspace_b, offer_id, client = _qualification_app(tmp_path)
    all_pass = {"status": "qualified", "account_eligibility": "pass", "geography_fit": "pass",
        "traffic_source_fit": "pass", "terms_review": "pass", "landing_page_review": "pass", "disclosure_review": "pass",
        "evidence_urls": ["https://merchant.example/affiliate-terms"],
        "notes": "Reviewed supplied evidence for this workspace; provider approval is not implied.", "policy_version": "manual-review-v2"}
    try:
        with client:
            initial = client.get("/api/offers/qualification-queue")
            assert initial.status_code == 200, initial.text
            assert initial.json()["total_count"] == 1
            item = initial.json()["data"][0]
            assert item["qualification"]["status"] == "not_reviewed"
            assert item["qualification"]["affiliate_network_approval_implied"] is False
            assert client.post(f"/api/offers/{offer_id}/qualification", json={**all_pass, "terms_review": "unknown"}).status_code == 422
            assert client.post(f"/api/offers/{offer_id}/qualification", json={**all_pass, "evidence_urls": []}).status_code == 422
            assert client.post(f"/api/offers/{offer_id}/qualification", json={**all_pass, "evidence_urls": ["https://127.0.0.1/internal"]}).status_code == 422
            saved = client.post(f"/api/offers/{offer_id}/qualification", json=all_pass)
            assert saved.status_code == 200, saved.text
            body = saved.json()
            assert body["status"] == "qualified" and body["reviewed_by"] == "reviewer@example.com"
            assert body["policy_version"] == "manual-review-v2" and body["activation_allowed"] is False
            assert body["evidence_basis"] == "operator_supplied_unverified" and body["affiliate_network_approval_implied"] is False
            assert client.get("/api/offers/qualification-queue").json()["total_count"] == 0
            all_offers = client.get("/api/offers/qualification-queue?status=all").json()
            assert all_offers["data"][0]["qualification"]["status"] == "qualified"
            user["workspace_id"] = workspace_b
            isolated = client.get("/api/offers/qualification-queue?status=all").json()
            assert isolated["data"][0]["qualification"]["status"] == "not_reviewed"
            user["workspace_role"] = "member"
            assert client.post(f"/api/offers/{offer_id}/qualification", json={**all_pass, "notes": "Member cannot decide."}).status_code == 403
    finally:
        _cleanup(engine, client)
