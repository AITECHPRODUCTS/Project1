from __future__ import annotations

import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


SECRET = "unsubscribe-test-secret-that-is-long-enough"


def _signed_params(lead_id: str, ts: int) -> dict[str, str]:
    signature = hmac.new(
        SECRET.encode(),
        f"unsubscribe:{lead_id}:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {"ts": str(ts), "sig": signature}


def _configure(monkeypatch):
    monkeypatch.setattr(
        main,
        "settings",
        SimpleNamespace(
            tracking_hmac_secret=SECRET,
            app_session_secret="fallback-session-secret",
        ),
    )
    db = SimpleNamespace()
    async def session_override():
        yield db
    monkeypatch.setitem(main.app.dependency_overrides, get_session, session_override)
    return db


def test_unsubscribe_get_is_non_mutating_and_returns_explicit_confirmation(monkeypatch):
    db = _configure(monkeypatch)
    unsub = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "unsubscribe_lead", unsub)
    lead_id = "lead-123"
    params = _signed_params(lead_id, int(time.time()))

    try:
        with TestClient(main.app) as client:
            response = client.get(f"/unsubscribe/{lead_id}", params=params)

        assert response.status_code == 200
        assert "Confirm unsubscribe" in response.text
        assert "select Unsubscribe to confirm" in response.text
        assert 'method="post"' in response.text
        assert f"ts={params['ts']}&amp;sig={params['sig']}" in response.text
        assert response.headers["cache-control"] == "no-store, max-age=0"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["content-security-policy"].startswith("default-src 'none'")
        unsub.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize(
    "body",
    ["List-Unsubscribe=One-Click", "confirm=unsubscribe"],
)
def test_unsubscribe_post_suppresses_only_after_valid_explicit_post(monkeypatch, body):
    db = _configure(monkeypatch)
    unsub = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "unsubscribe_lead", unsub)
    lead_id = "lead-123"
    params = _signed_params(lead_id, int(time.time()))

    try:
        with TestClient(main.app) as client:
            response = client.post(
                f"/unsubscribe/{lead_id}",
                params=params,
                data=body,
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

        assert response.status_code == 200
        assert "You are unsubscribed" in response.text
        unsub.assert_awaited_once_with(db, lead_id)
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_unsubscribe_post_rejects_invalid_form_without_mutation(monkeypatch):
    _configure(monkeypatch)
    unsub = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "unsubscribe_lead", unsub)
    params = _signed_params("lead-123", int(time.time()))

    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/unsubscribe/lead-123",
                params=params,
                data="confirm=yes",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert response.status_code == 400
        unsub.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_unsubscribe_post_rejects_missing_or_wrong_content_type(monkeypatch):
    _configure(monkeypatch)
    unsub = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "unsubscribe_lead", unsub)
    params = _signed_params("lead-123", int(time.time()))

    try:
        with TestClient(main.app) as client:
            response = client.post("/unsubscribe/lead-123", params=params, json={"confirm": "unsubscribe"})
        assert response.status_code == 415
        unsub.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_unsubscribe_post_rejects_oversized_body_before_mutation(monkeypatch):
    _configure(monkeypatch)
    unsub = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "unsubscribe_lead", unsub)
    params = _signed_params("lead-123", int(time.time()))

    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/unsubscribe/lead-123",
                params=params,
                content=b"x" * 4097,
                headers={
                    "content-type": "application/x-www-form-urlencoded",
                    "content-length": "4097",
                },
            )
        assert response.status_code == 413
        unsub.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_unsubscribe_links_reject_bad_signature_and_expired_timestamp(monkeypatch):
    _configure(monkeypatch)
    unsub = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "unsubscribe_lead", unsub)
    stale = _signed_params("lead-123", int(time.time()) - 31_536_001)
    bad = {**_signed_params("lead-123", int(time.time())), "sig": "0" * 64}

    try:
        with TestClient(main.app) as client:
            expired = client.get("/unsubscribe/lead-123", params=stale)
            invalid = client.get("/unsubscribe/lead-123", params=bad)
            invalid_post = client.post(
                "/unsubscribe/lead-123",
                params=bad,
                data="List-Unsubscribe=One-Click",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert expired.status_code == 410
        assert invalid.status_code == 403
        assert invalid_post.status_code == 403
        unsub.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
