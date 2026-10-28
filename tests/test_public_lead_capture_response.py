from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


def _override_session(session):
    async def override_get_session():
        yield session
    return override_get_session


def _install(monkeypatch, result):
    session = object()
    monkeypatch.setattr(main, "public_rate_limit", AsyncMock(return_value=None))
    monkeypatch.setattr(main, "verify_workspace_token", lambda token, purpose: "workspace-test")
    monkeypatch.setattr(main, "create_lead", AsyncMock(return_value=result))
    main.app.dependency_overrides[get_session] = _override_session(session)
    return session


def _payload():
    return {
        "email": "reader@example.invalid",
        "consent": True,
        "lead_magnet": "A helpful guide",
        "audience": "independent creators",
        "workspace_token": "signed-workspace-token",
    }


def test_public_signup_html_does_not_claim_marketing_is_queued_before_confirmation(monkeypatch):
    _install(monkeypatch, {
        "status": "confirmation_pending", "lead_id": "lead-1",
        "emails_scheduled": 0, "confirmation_email_sent": True,
    })
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/public/leads/capture", json=_payload())
        assert response.status_code == 202
        assert "Check your email to confirm" in response.text
        assert "No marketing email sequence will be sent until you confirm" in response.text
        assert "Your consent-based email sequence was queued." not in response.text
        assert response.headers["cache-control"] == "no-store"
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_public_signup_html_reports_confirmation_delivery_failure_honestly(monkeypatch):
    _install(monkeypatch, {
        "status": "confirmation_delivery_failed", "lead_id": "lead-2",
        "emails_scheduled": 0, "confirmation_email_sent": False,
    })
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/public/leads/capture", json=_payload())
        assert response.status_code == 503
        assert "couldn't send the confirmation email" in response.text
        assert "No marketing emails were queued" in response.text
        assert "Your consent-based email sequence was queued." not in response.text
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_public_signup_json_returns_pending_and_failed_states_with_accurate_http_codes(monkeypatch):
    cases = [
        ({"status": "confirmation_pending", "lead_id": "lead-3", "emails_scheduled": 0}, 202),
        ({"status": "confirmation_delivery_failed", "lead_id": "lead-4", "emails_scheduled": 0}, 503),
        ({"status": "confirmation_already_pending", "lead_id": "lead-5", "emails_scheduled": 0}, 202),
    ]
    for result, expected_status in cases:
        _install(monkeypatch, result)
        try:
            with TestClient(main.app) as client:
                response = client.post(
                    "/api/public/leads/capture", json=_payload(),
                    headers={"accept": "application/json"},
                )
            assert response.status_code == expected_status
            assert response.json()["status"] == result["status"]
            assert response.json()["emails_scheduled"] == 0
        finally:
            main.app.dependency_overrides.pop(get_session, None)


def test_public_signup_html_only_reports_queued_when_messages_exist(monkeypatch):
    _install(monkeypatch, {
        "lead_id": "lead-6", "emails_scheduled": 3, "status": "scheduled",
    })
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/public/leads/capture", json=_payload())
        assert response.status_code == 201
        assert "You're on the list" in response.text
        assert "Your consent-based email sequence was queued." in response.text
    finally:
        main.app.dependency_overrides.pop(get_session, None)
