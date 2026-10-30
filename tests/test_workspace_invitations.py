from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from backend import main
from backend.database import Base, get_session
from backend.models import AuditLog, UserAccount, Workspace, WorkspaceInvitation, WorkspaceMembership

WORKSPACE_ID = "10000000-0000-4000-8000-000000000101"
HOME_WORKSPACE_ID = "10000000-0000-4000-8000-000000000102"
OWNER_ID = "owner-user-101"
ADMIN_ID = "admin-user-101"
INVITEE_ID = "invitee-user-101"
OTHER_ID = "other-user-101"


async def _setup(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    state = {"user": {"email": "owner@example.test", "user_id": OWNER_ID, "workspace_id": WORKSPACE_ID, "workspace_role": "owner", "is_admin": False}}

    async def override_session():
        async with sessions() as db:
            yield db

    async def current_user(request: Request):
        session_user = request.session.get("user")
        return dict(session_user) if isinstance(session_user, dict) else dict(state["user"])

    monkeypatch.setitem(main.app.dependency_overrides, get_session, override_session)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, current_user)
    async with sessions() as db:
        db.add_all([
            UserAccount(id=OWNER_ID, email="owner@example.test", password_hash="unused-test-hash", is_admin=False, is_active=True),
            UserAccount(id=ADMIN_ID, email="admin@example.test", password_hash="unused-test-hash", is_admin=False, is_active=True),
            UserAccount(id=INVITEE_ID, email="invitee@example.test", password_hash="unused-test-hash", is_admin=False, is_active=True),
            UserAccount(id=OTHER_ID, email="other@example.test", password_hash="unused-test-hash", is_admin=False, is_active=True),
            Workspace(id=WORKSPACE_ID, name="Publisher workspace", slug="publisher-workspace", owner_user_id=OWNER_ID),
            Workspace(id=HOME_WORKSPACE_ID, name="Invitee home workspace", slug="invitee-home-workspace", owner_user_id=INVITEE_ID),
            WorkspaceMembership(workspace_id=WORKSPACE_ID, user_id=OWNER_ID, role="owner", is_active=True),
            WorkspaceMembership(workspace_id=WORKSPACE_ID, user_id=ADMIN_ID, role="admin", is_active=True),
            WorkspaceMembership(workspace_id=HOME_WORKSPACE_ID, user_id=INVITEE_ID, role="owner", is_active=True),
            WorkspaceMembership(workspace_id=HOME_WORKSPACE_ID, user_id=OTHER_ID, role="owner", is_active=True),
        ])
        await db.commit()
    return engine, sessions, state


def test_owner_can_create_list_revoke_invitation_and_token_is_not_listed(monkeypatch):
    engine, sessions, state = asyncio.run(_setup(monkeypatch))
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/workspaces/invitations", json={"email": " Invitee@Example.Test ", "role": "member", "expires_in_hours": 48})
            assert created.status_code == 201, created.text
            payload = created.json()
            assert payload["email"] == "invitee@example.test" and payload["role"] == "member"
            assert payload["delivery"] == "manual_link_only" and payload["token"]
            listing = client.get("/api/workspaces/invitations")
            assert listing.status_code == 200, listing.text
            row = listing.json()["data"][0]
            assert row["status"] == "pending" and "token" not in row and "token_hash" not in row
            assert listing.json()["delivery"] == "manual_link_only"
            assert "not sent by this endpoint" in listing.json()["note"].lower()
            revoked = client.post(f"/api/workspaces/invitations/{payload['id']}/revoke")
            assert revoked.status_code == 200, revoked.text
            assert revoked.json()["status"] == "revoked"
            rejected = client.post("/api/workspaces/invitations/accept", json={"token": payload["token"]})
            assert rejected.status_code == 410, rejected.text
    finally:
        asyncio.run(engine.dispose())


def test_workspace_admin_cannot_invite_admin_and_members_cannot_manage_invites(monkeypatch):
    engine, sessions, state = asyncio.run(_setup(monkeypatch))
    try:
        state["user"] = {"email": "admin@example.test", "user_id": ADMIN_ID, "workspace_id": WORKSPACE_ID, "workspace_role": "admin", "is_admin": False}
        with TestClient(main.app) as client:
            elevated = client.post("/api/workspaces/invitations", json={"email": "other@example.test", "role": "admin"})
            assert elevated.status_code == 403, elevated.text
            state["user"] = {"email": "invitee@example.test", "user_id": INVITEE_ID, "workspace_id": WORKSPACE_ID, "workspace_role": "member", "is_admin": False}
            denied = client.get("/api/workspaces/invitations")
            assert denied.status_code == 403, denied.text
    finally:
        asyncio.run(engine.dispose())


def test_acceptance_requires_matching_email_creates_membership_and_rejects_replay(monkeypatch):
    engine, sessions, state = asyncio.run(_setup(monkeypatch))
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/workspaces/invitations", json={"email": "invitee@example.test", "role": "viewer"})
            assert created.status_code == 201, created.text
            token = created.json()["token"]
            state["user"] = {"email": "other@example.test", "user_id": OTHER_ID, "workspace_id": HOME_WORKSPACE_ID, "workspace_role": "owner", "is_admin": False}
            mismatch = client.post("/api/workspaces/invitations/accept", json={"token": token})
            assert mismatch.status_code == 403, mismatch.text
            state["user"] = {"email": "invitee@example.test", "user_id": INVITEE_ID, "workspace_id": HOME_WORKSPACE_ID, "workspace_role": "owner", "is_admin": False}
            accepted = client.post("/api/workspaces/invitations/accept", json={"token": token})
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["active_workspace_id"] == WORKSPACE_ID
            assert accepted.json()["role"] == "viewer" and accepted.json()["csrf_token"]
            current = client.get("/api/workspaces/current")
            assert current.status_code == 200 and current.json()["id"] == WORKSPACE_ID
            replay = client.post(
                "/api/workspaces/invitations/accept",
                json={"token": token},
                headers={"X-CSRF-Token": accepted.json()["csrf_token"]},
            )
            assert replay.status_code == 409, replay.text
        async def verify_db():
            async with sessions() as db:
                member = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == WORKSPACE_ID, WorkspaceMembership.user_id == INVITEE_ID))
                invitation = await db.scalar(select(WorkspaceInvitation).where(WorkspaceInvitation.email == "invitee@example.test"))
                audits = list((await db.scalars(select(AuditLog).where(AuditLog.workspace_id == WORKSPACE_ID, AuditLog.action == "workspace.invitation.accepted"))).all())
                return member, invitation, audits
        member, invitation, audits = asyncio.run(verify_db())
        assert member is not None and member.is_active and member.role == "viewer"
        assert invitation is not None and invitation.accepted_at is not None
        assert len(audits) == 1
        assert invitation.token_hash != token
    finally:
        asyncio.run(engine.dispose())


def test_expired_invitation_is_rejected(monkeypatch):
    engine, sessions, state = asyncio.run(_setup(monkeypatch))
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/workspaces/invitations", json={"email": "invitee@example.test", "role": "member"})
            assert created.status_code == 201, created.text
            token = created.json()["token"]
            async def expire():
                async with sessions() as db:
                    invitation = await db.scalar(select(WorkspaceInvitation).where(WorkspaceInvitation.email == "invitee@example.test"))
                    invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
                    await db.commit()
            asyncio.run(expire())
            state["user"] = {"email": "invitee@example.test", "user_id": INVITEE_ID, "workspace_id": HOME_WORKSPACE_ID, "workspace_role": "owner", "is_admin": False}
            rejected = client.post("/api/workspaces/invitations/accept", json={"token": token})
            assert rejected.status_code == 410, rejected.text
    finally:
        asyncio.run(engine.dispose())
