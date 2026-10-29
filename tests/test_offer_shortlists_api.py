from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base, get_session
from backend.models import Offer, Workspace


def _shortlist_test_app(tmp_path, database_name):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / database_name}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            a = Workspace(name="Workspace A", slug="workspace-a")
            b = Workspace(name="Workspace B", slug="workspace-b")
            db.add_all([a, b])
            await db.flush()
            offer = Offer(network="openaffiliate", external_id="creator-suite", name="Creator Suite",
                description="Email and analytics tools", category="creator", reward_type="recurring_percentage",
                reward_value="20", cookie_days=45, epc=None, conversion_rate=None, verified=True,
                source_url="https://provider.example/creator-suite")
            db.add(offer)
            await db.commit()
            return a.id, b.id, offer.id
    workspace_a, workspace_b, offer_id = asyncio.run(setup())
    user = {"workspace_id": workspace_a, "workspace_role": "owner", "email": "a@example.com", "user_id": "a", "is_admin": False}
    async def override_session():
        async with sessions() as db:
            yield db
    async def override_auth():
        return user
    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    return engine, user, workspace_a, workspace_b, offer_id, TestClient(main.app)


def _shortlist_cleanup(engine, client):
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)
    client.close()
    asyncio.run(engine.dispose())


def test_saved_offer_shortlist_lifecycle_and_current_catalog_evidence(tmp_path):
    engine, user, _, _, offer_id, client = _shortlist_test_app(tmp_path, "shortlists.db")
    try:
        with client:
            created = client.post("/api/offers/shortlists", json={"name": "  Q4 research  ", "description": "  Compare evidence, not guesses. "})
            assert created.status_code == 201, created.text
            shortlist = created.json()
            assert shortlist["name"] == "Q4 research"
            assert shortlist["description"] == "Compare evidence, not guesses."
            assert client.post("/api/offers/shortlists", json={"name": "Q4 research"}).status_code == 409
            added = client.post(f"/api/offers/shortlists/{shortlist['id']}/items", json={"offer_id": offer_id, "note": "  Verify terms before use. "})
            assert added.status_code == 201, added.text
            assert added.json()["note"] == "Verify terms before use."
            assert client.post(f"/api/offers/shortlists/{shortlist['id']}/items", json={"offer_id": offer_id}).status_code == 409
            detail = client.get(f"/api/offers/shortlists/{shortlist['id']}")
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body["count"] == 1
            assert body["items"][0]["offer"]["epc"] is None
            assert body["items"][0]["offer"]["verification_basis"] == "provider_claimed_unattested"
            assert body["items"][0]["note"] == "Verify terms before use."
            assert client.get("/api/offers/shortlists").json()["data"][0]["item_count"] == 1
            assert client.delete(f"/api/offers/shortlists/{shortlist['id']}/items/{offer_id}").status_code == 200
            assert client.get(f"/api/offers/shortlists/{shortlist['id']}").json()["count"] == 0
            assert client.delete(f"/api/offers/shortlists/{shortlist['id']}").status_code == 200
            assert client.get(f"/api/offers/shortlists/{shortlist['id']}").status_code == 404
    finally:
        _shortlist_cleanup(engine, client)


def test_saved_offer_shortlists_are_isolated_between_workspaces(tmp_path):
    engine, user, _, workspace_b, _, client = _shortlist_test_app(tmp_path, "shortlists-tenant.db")
    try:
        with client:
            created = client.post("/api/offers/shortlists", json={"name": "Private list"})
            assert created.status_code == 201, created.text
            shortlist_id = created.json()["id"]
            user["workspace_id"] = workspace_b
            assert client.get("/api/offers/shortlists").json()["count"] == 0
            assert client.get(f"/api/offers/shortlists/{shortlist_id}").status_code == 404
            assert client.delete(f"/api/offers/shortlists/{shortlist_id}").status_code == 404
            user["workspace_id"] = None
            assert client.post("/api/offers/shortlists", json={"name": "No workspace"}).status_code == 403
    finally:
        _shortlist_cleanup(engine, client)
