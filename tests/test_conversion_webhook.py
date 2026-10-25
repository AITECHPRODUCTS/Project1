from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session


SECRET = "conversion-webhook-test-secret-with-32-plus-characters"


def signed_headers(body: bytes, secret: str = SECRET) -> dict[str, str]:
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {"X-Affiliate-Signature": f"sha256={signature}", "Content-Type": "application/json"}


def fake_session(*scalar_results):
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=list(scalar_results)),
        add=Mock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    async def override_get_session():
        yield session

    return session, override_get_session


def test_conversion_webhook_rejects_invalid_signature_before_database_access(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    session, override = fake_session()
    main.app.dependency_overrides[get_session] = override
    try:
        with TestClient(main.app) as client:
            body = json.dumps({"event_id": "evt-invalid", "click_id": "click-1"}).encode()
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers={"X-Affiliate-Signature": "sha256=" + ("0" * 64)},
            )
        assert response.status_code == 401
        session.scalar.assert_not_awaited()
        session.add.assert_not_called()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_requires_configured_strong_secret(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", "short")
    session, override = fake_session()
    main.app.dependency_overrides[get_session] = override
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=b'{"event_id":"evt-1"}',
                headers={"X-Affiliate-Signature": "0" * 64},
            )
        assert response.status_code == 503
        session.scalar.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_persists_verified_event_for_resolved_click(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    click = SimpleNamespace(click_id="click-1", workspace_id="workspace-1")
    session, override = fake_session(click, None)
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {
            "event_id": "evt-verified-1",
            "click_id": "click-1",
            "commission": "1.25",
            "revenue": "9.50",
            "currency": "USD",
            "status": "approved",
        },
        separators=(",", ":"),
    ).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers=signed_headers(body),
            )
        assert response.status_code == 200
        assert response.json()["status"] == "recorded"
        assert response.json()["reversal"] is False
        session.commit.assert_awaited_once()
        session.add.assert_called_once()
        row = session.add.call_args.args[0]
        assert row.network == "example-network"
        assert row.external_event_id == "evt-verified-1"
        assert row.click_id == "click-1"
        assert row.workspace_id == "workspace-1"
        assert row.commission == 1.25
        assert row.revenue == 9.5
        assert row.currency == "USD"
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_quarantines_unknown_click_without_persisting(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    session, override = fake_session(None)
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {"event_id": "evt-unmatched", "click_id": "unknown-click", "commission": "2.00"},
        separators=(",", ":"),
    ).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers=signed_headers(body),
            )
        assert response.status_code == 202
        assert response.json()["status"] == "unmatched_quarantined"
        assert response.json()["stored"] is False
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_ignores_duplicate_provider_event(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    click = SimpleNamespace(click_id="click-1", workspace_id="workspace-1")
    existing = SimpleNamespace(id="existing-conversion")
    session, override = fake_session(click, existing)
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {"event_id": "evt-duplicate", "click_id": "click-1", "commission": "1.00"},
        separators=(",", ":"),
    ).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers=signed_headers(body),
            )
        assert response.status_code == 200
        assert response.json()["status"] == "duplicate_ignored"
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)
