from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


def _override(session):
    async def override_get_session():
        yield session
    return override_get_session


def test_confirmation_get_is_scanner_safe_and_does_not_confirm(monkeypatch):
    token = "A" * 43
    row = SimpleNamespace(status="sent", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    db = SimpleNamespace(scalar=AsyncMock(return_value=row), commit=AsyncMock(), add=AsyncMock())
    confirmed = AsyncMock()
    monkeypatch.setattr(main, "confirm_email_consent", confirmed)
    monkeypatch.setattr(main, "public_rate_limit", AsyncMock(return_value=None))
    main.app.dependency_overrides[get_session] = _override(db)
    try:
        with TestClient(main.app) as client:
            response = client.get("/email-consent/confirm", params={"token": token})
        assert response.status_code == 200
        assert "Opening this page does not change your consent" in response.text
        assert 'method="post"' in response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        confirmed.assert_not_awaited()
        db.commit.assert_not_awaited()
        db.add.assert_not_called()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_confirmation_post_requires_explicit_urlencoded_form(monkeypatch):
    token = "A" * 43
    db = SimpleNamespace()
    confirmed = AsyncMock(return_value={"status": "confirmed", "lead_id": "lead-1", "emails_scheduled": 1})
    monkeypatch.setattr(main, "confirm_email_consent", confirmed)
    monkeypatch.setattr(main, "public_rate_limit", AsyncMock(return_value=None))
    main.app.dependency_overrides[get_session] = _override(db)
    try:
        with TestClient(main.app) as client:
            wrong_type = client.post("/email-consent/confirm", json={"token": token, "confirm": "yes"})
            missing_confirmation = client.post(
                "/email-consent/confirm", content=f"token={token}",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            accepted = client.post(
                "/email-consent/confirm", data={"token": token, "confirm": "yes"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        assert wrong_type.status_code == 415
        assert missing_confirmation.status_code == 400
        assert accepted.status_code == 200
        confirmed.assert_awaited_once_with(db, token)
        assert "Email address confirmed" in accepted.text
    finally:
        main.app.dependency_overrides.pop(get_session, None)
