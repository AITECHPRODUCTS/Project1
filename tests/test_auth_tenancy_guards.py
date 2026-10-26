from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend import main


class _NoMembershipDatabase:
    async def scalar(self, statement):
        return None


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
