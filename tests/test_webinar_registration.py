from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend import main
from backend.database import Base, get_session
from backend.models import Workspace

@pytest.fixture
def webinar_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'webinars.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            workspace = Workspace(name="Webinar Workspace", slug="webinar-test-workspace")
            db.add(workspace)
            await db.flush()
            workspace_id = workspace.id
            await db.commit()
        await engine.dispose()
        return workspace_id
    workspace_id = asyncio.run(setup())
    auth_user = {"workspace_id": workspace_id, "workspace_role": "owner", "email": "webinar-owner@example.com", "is_admin": False}
    async def override_session():
        async with sessions() as db:
            yield db
    async def override_auth():
        return auth_user
    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[main.require_auth] = override_auth
    try:
        with TestClient(main.app) as client:
            yield client, auth_user
    finally:
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.require_auth, None)
        asyncio.run(engine.dispose())

def event_payload():
    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=1)
    deadline = start - timedelta(days=1)
    return {
        "title": "Affiliate Growth Webinar",
        "summary": "Learn a reliable system for compliant affiliate growth.",
        "description": "A detailed event description long enough to explain webinar objectives and agenda.",
        "host_name": "Product Education Team", "host_bio": "A host biography supplied by the organizer.",
        "start_at": start.isoformat(), "end_at": end.isoformat(), "timezone_name": "Asia/Kolkata",
        "registration_deadline": deadline.isoformat(), "capacity": 1,
        "agenda_items": [{"title": "Offer research", "description": "Evaluate source evidence."}],
        "privacy_policy_url": "https://example.com/privacy",
        "consent_text": "I agree to the use of my information to administer this webinar.",
        "affiliate_disclosure": "Disclosure: the organizer may use affiliate links.",
    }

def test_webinar_page_is_draft_until_owner_opens_registration(webinar_client):
    client, _ = webinar_client
    created = client.post("/api/webinars", json=event_payload())
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["status"] == "draft" and event["public_registration_open"] is False
    assert event["external_webinar_provider"] == "not_configured"
    assert client.get(f"/api/public/webinars/{event['public_id']}").status_code == 404
    opened = client.post(f"/api/webinars/{event['id']}/open", json={})
    assert opened.status_code == 200, opened.text
    page = client.get(f"/api/public/webinars/{event['public_id']}")
    assert page.status_code == 200, page.text
    assert page.json()["title"] == event["title"]
    assert page.json()["agenda_items"][0]["title"] == "Offer research"

def test_public_registration_records_consent_deduplicates_and_enforces_capacity(webinar_client):
    client, _ = webinar_client
    created = client.post("/api/webinars", json=event_payload()).json()
    assert client.post(f"/api/webinars/{created['id']}/open", json={}).status_code == 200
    url = f"/api/public/webinars/{created['public_id']}/register"
    denied = client.post(url, json={"full_name":"Test Registrant","email":"user@example.com","consent":False})
    assert denied.status_code == 422, denied.text
    payload = {"full_name":"Test Registrant","email":"User@example.com","consent":True}
    first = client.post(url, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["consent_recorded"] is True and first.json()["email_confirmation_sent"] is False
    duplicate = client.post(url, json=payload)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "already_registered"
    full = client.post(url, json={"full_name":"Another Person","email":"another@example.com","consent":True})
    assert full.status_code == 409, full.text

def test_non_admin_workspace_member_cannot_open_public_registrations(webinar_client):
    client, user = webinar_client
    created = client.post("/api/webinars", json=event_payload())
    assert created.status_code == 201, created.text
    user["workspace_role"] = "member"
    response = client.post(f"/api/webinars/{created.json()['id']}/open", json={})
    assert response.status_code == 403
