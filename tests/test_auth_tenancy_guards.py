from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend import main


class _AuthDatabase:
    def __init__(self, *, account=None, membership=None, workspace=None):
        self.account = account
        self.membership = membership
        self.workspace = workspace
        self.membership_queries = 0

    async def get(self, model, identity):
        if model is main.UserAccount:
            return self.account
        if model is main.Workspace:
            return self.workspace or SimpleNamespace(id=identity, lifecycle_state="active")
        return None

    async def scalar(self, statement):
        self.membership_queries += 1
        return self.membership


class _NoMembershipDatabase(_AuthDatabase):
    def __init__(self):
        super().__init__(
            account=SimpleNamespace(
                id="revoked-user",
                email="user@example.invalid",
                is_active=True,
                is_admin=False,
            ),
            membership=None,
        )


def _request(*, session: dict, authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization:
        headers.append((b"authorization", authorization.encode("latin-1")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/api/test",
        "raw_path": b"/api/test",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 12345),
        "server": ("testserver", 443),
        "session": session,
        "app": main.app,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_revoked_workspace_membership_invalidates_existing_session(monkeypatch):
    # Avoid the development-only local auto-login while exercising the real guard.
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "")
    session = {
        "user": {
            "user_id": "revoked-user",
            "workspace_id": "revoked-workspace",
            "is_admin": False,
            "workspace_role": "owner",
        },
        "csrf_token": "stale-csrf-token",
    }
    request = _request(session=session)

    with pytest.raises(HTTPException) as error:
        await main.require_auth(request, _NoMembershipDatabase())

    assert error.value.status_code == 403
    assert error.value.detail == "Workspace membership is no longer active"
    assert request.session == {}


@pytest.mark.asyncio
async def test_static_api_token_is_rejected_for_workspace_scoped_access(monkeypatch):
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "test-static-api-token")
    request = _request(session={}, authorization="Bearer test-static-api-token")

    with pytest.raises(HTTPException) as error:
        await main.require_auth(request, _NoMembershipDatabase())

    assert error.value.status_code == 403
    assert "not workspace-scoped" in error.value.detail


@pytest.mark.asyncio
async def test_workspace_member_cannot_use_workspace_admin_dependency():
    user = {"is_admin": False, "workspace_role": "member", "user_id": "member-1"}

    with pytest.raises(HTTPException) as error:
        await main.require_admin(user)

    assert error.value.status_code == 403
    assert error.value.detail == "Workspace owner/admin permission required"


@pytest.mark.asyncio
async def test_platform_admin_revocation_is_reflected_in_an_existing_session(monkeypatch):
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "")
    session = {
        "user": {
            "user_id": "admin-user",
            "workspace_id": "admin-workspace",
            "is_admin": True,
            "workspace_role": "owner",
            "email": "stale@example.invalid",
        },
        "csrf_token": "existing-csrf-token",
    }
    request = _request(session=session)
    db = _AuthDatabase(
        account=SimpleNamespace(
            id="admin-user",
            email="current@example.invalid",
            is_active=True,
            is_admin=False,
        ),
        membership=SimpleNamespace(role="owner", is_active=True),
    )

    user = await main.require_auth(request, db)

    assert user["is_admin"] is False
    assert user["email"] == "current@example.invalid"
    assert request.session["user"]["is_admin"] is False
    with pytest.raises(HTTPException) as error:
        await main.require_platform_admin(user)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_suspended_account_invalidates_existing_session_before_membership_lookup(monkeypatch):
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "")
    session = {
        "user": {
            "user_id": "suspended-user",
            "workspace_id": "suspended-workspace",
            "is_admin": True,
            "workspace_role": "owner",
        },
        "csrf_token": "stale-csrf-token",
    }
    request = _request(session=session)
    db = _AuthDatabase(
        account=SimpleNamespace(
            id="suspended-user",
            email="suspended@example.invalid",
            is_active=False,
            is_admin=True,
        ),
        membership=SimpleNamespace(role="owner", is_active=True),
    )

    with pytest.raises(HTTPException) as error:
        await main.require_auth(request, db)

    assert error.value.status_code == 403
    assert error.value.detail == "Account is inactive or no longer available"
    assert request.session == {}
    assert db.membership_queries == 0


@pytest.mark.asyncio
async def test_missing_account_invalidates_existing_session_fail_closed(monkeypatch):
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "")
    session = {
        "user": {
            "user_id": "deleted-user",
            "workspace_id": "deleted-workspace",
            "is_admin": True,
            "workspace_role": "owner",
        },
        "csrf_token": "stale-csrf-token",
    }
    request = _request(session=session)
    db = _AuthDatabase(account=None, membership=SimpleNamespace(role="owner", is_active=True))

    with pytest.raises(HTTPException) as error:
        await main.require_auth(request, db)

    assert error.value.status_code == 403
    assert request.session == {}
    assert db.membership_queries == 0


@pytest.mark.asyncio
async def test_new_platform_admin_grant_is_reflected_without_relogin(monkeypatch):
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "")
    session = {
        "user": {
            "user_id": "new-admin-user",
            "workspace_id": "admin-workspace",
            "is_admin": False,
            "workspace_role": "member",
        },
        "csrf_token": "existing-csrf-token",
    }
    request = _request(session=session)
    db = _AuthDatabase(
        account=SimpleNamespace(
            id="new-admin-user",
            email="new-admin@example.invalid",
            is_active=True,
            is_admin=True,
        ),
        membership=SimpleNamespace(role="member", is_active=True),
    )

    user = await main.require_auth(request, db)

    assert user["is_admin"] is True
    assert request.session["user"]["is_admin"] is True
    assert await main.require_platform_admin(user) is user



@pytest.mark.asyncio
async def test_suspended_workspace_invalidates_existing_session_before_membership_lookup(monkeypatch):
    monkeypatch.setattr(main.settings, "initial_admin_email", "bootstrap@example.test")
    monkeypatch.setattr(main.settings, "api_access_token", "")
    session = {
        "user": {
            "user_id": "suspended-tenant-user",
            "workspace_id": "suspended-workspace",
            "is_admin": False,
            "workspace_role": "owner",
        },
        "csrf_token": "existing-csrf-token",
    }
    request = _request(session=session)
    db = _AuthDatabase(
        account=SimpleNamespace(
            id="suspended-tenant-user",
            email="user@example.invalid",
            is_active=True,
            is_admin=False,
        ),
        membership=SimpleNamespace(role="owner", is_active=True),
        workspace=SimpleNamespace(id="suspended-workspace", lifecycle_state="suspended"),
    )

    with pytest.raises(HTTPException) as error:
        await main.require_auth(request, db)

    assert error.value.status_code == 403
    assert "Workspace is suspended or unavailable" in error.value.detail
    assert request.session == {}
    assert db.membership_queries == 0

