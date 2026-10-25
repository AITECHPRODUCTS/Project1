from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from sqlalchemy.exc import IntegrityError

from fastapi.testclient import TestClient

from backend import main
from backend.config import Settings
from backend.database import get_session
from backend.models import Conversion, ConversionLedgerEntry
from decimal import Decimal
import pytest


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
        assert session.add.call_count == 2
        added = [call.args[0] for call in session.add.call_args_list]
        row = next(value for value in added if isinstance(value, Conversion))
        ledger_entry = next(value for value in added if isinstance(value, ConversionLedgerEntry))
        assert row.network == "example-network"
        assert row.external_event_id == "evt-verified-1"
        assert row.click_id == "click-1"
        assert row.workspace_id == "workspace-1"
        assert row.commission == 1.25
        assert row.revenue == 9.5
        assert row.currency == "USD"
        assert ledger_entry.workspace_id == "workspace-1"
        assert ledger_entry.network == "example-network"
        assert ledger_entry.external_event_id == "evt-verified-1"
        assert ledger_entry.entry_type == "conversion"
        assert ledger_entry.commission_amount == Decimal("1.250000")
        assert ledger_entry.revenue_amount == Decimal("9.500000")
        assert ledger_entry.evidence_status == "signed_webhook_verified"
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



def test_conversion_webhook_treats_commit_race_as_duplicate_only_when_row_exists(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    click = SimpleNamespace(click_id="click-1", workspace_id="workspace-1")
    session, override = fake_session(click, None, "existing-conversion")
    session.commit = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("unique conflict")))
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {"event_id": "evt-race", "click_id": "click-1", "commission": "1.00"},
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
        session.rollback.assert_awaited_once()
        assert session.scalar.await_count == 3
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_does_not_hide_unrelated_integrity_errors(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    click = SimpleNamespace(click_id="click-1", workspace_id="workspace-1")
    session, override = fake_session(click, None, None)
    session.commit = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("foreign key conflict")))
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {"event_id": "evt-integrity-error", "click_id": "click-1", "commission": "1.00"},
        separators=(",", ":"),
    ).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers=signed_headers(body),
            )
        assert response.status_code == 409
        assert "integrity conflict" in response.json()["detail"]
        session.rollback.assert_awaited_once()
        assert session.scalar.await_count == 3
    finally:
        main.app.dependency_overrides.pop(get_session, None)



def test_conversion_webhook_rejects_oversized_body_before_database_access(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    session, override = fake_session()
    main.app.dependency_overrides[get_session] = override
    body = b"x" * (main.MAX_AFFILIATE_WEBHOOK_BODY_BYTES + 1)
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers=signed_headers(body),
            )
        assert response.status_code == 413
        assert response.json()["detail"] == "Affiliate webhook body exceeds the size limit"
        session.scalar.assert_not_awaited()
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_rejects_streamed_oversize_body_without_content_length(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    session, override = fake_session()
    main.app.dependency_overrides[get_session] = override
    first = b'{"event_id":"evt-streamed","click_id":"click-1"}'
    second = b" " * main.MAX_AFFILIATE_WEBHOOK_BODY_BYTES
    body = first + second
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=iter([first, second]),
                headers=signed_headers(body),
            )
        assert response.status_code == 413
        session.scalar.assert_not_awaited()
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)



def test_conversion_webhook_reverses_original_once_under_row_lock(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    click = SimpleNamespace(click_id="click-refund", workspace_id="workspace-1")
    parent = SimpleNamespace(
        id="original-conversion", status="approved", commission=1.25, revenue=9.50
    )
    session, override = fake_session(click, None, parent)
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {
            "event_id": "evt-refund-1",
            "click_id": "click-refund",
            "status": "refunded",
            "original_event_id": "evt-original-1",
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
        assert response.json()["reversal"] is True
        assert response.json()["commission_adjustment"] == -1.25
        assert parent.status == "reversed"
        session.add.assert_called_once()
        reversal = session.add.call_args.args[0]
        assert reversal.status == "reversed"
        assert reversal.commission == -1.25
        assert reversal.revenue == -9.50
        assert reversal.event_json["original_event_id"] == "evt-original-1"
        assert "FOR UPDATE" in str(session.scalar.await_args_list[2].args[0]).upper()
        session.commit.assert_awaited_once()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_ignores_second_reversal_for_already_reversed_parent(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    click = SimpleNamespace(click_id="click-refund", workspace_id="workspace-1")
    parent = SimpleNamespace(
        id="original-conversion", status="reversed", commission=-1.25, revenue=-9.50
    )
    session, override = fake_session(click, None, parent)
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {
            "event_id": "evt-refund-2",
            "click_id": "click-refund",
            "status": "chargeback",
            "original_event_id": "evt-original-1",
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
        assert response.json()["status"] == "duplicate_reversal_ignored"
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


NETWORK_SECRET = "unique-network-secret-that-is-at-least-32-bytes"


def test_settings_normalize_per_network_webhook_secret_names():
    configured = Settings(
        _env_file=None,
        app_env="test",
        affiliate_webhook_secrets={" Example-Network ": NETWORK_SECRET},
    )
    assert configured.affiliate_webhook_secrets == {"example-network": NETWORK_SECRET}


def test_settings_reject_short_per_network_webhook_secrets():
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            _env_file=None,
            app_env="test",
            affiliate_webhook_secrets={"example-network": "too-short"},
        )


def test_conversion_webhook_per_network_secret_disables_shared_fallback(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    monkeypatch.setattr(main.settings, "affiliate_webhook_secrets", {"example-network": NETWORK_SECRET})
    session, override = fake_session()
    main.app.dependency_overrides[get_session] = override
    body = json.dumps({"event_id": "evt-wrong-network-key", "click_id": "click-1"}).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/example-network",
                content=body,
                headers=signed_headers(body, secret=SECRET),
            )
        assert response.status_code == 401
        session.scalar.assert_not_awaited()
        session.add.assert_not_called()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_fails_closed_for_unmapped_network_when_map_is_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    monkeypatch.setattr(main.settings, "affiliate_webhook_secrets", {"example-network": NETWORK_SECRET})
    session, override = fake_session()
    main.app.dependency_overrides[get_session] = override
    body = json.dumps({"event_id": "evt-unmapped-network", "click_id": "click-1"}).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/another-network",
                content=body,
                headers=signed_headers(body, secret=SECRET),
            )
        assert response.status_code == 503
        assert "not configured for this network" in response.json()["detail"]
        session.scalar.assert_not_awaited()
        session.add.assert_not_called()
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_conversion_webhook_accepts_network_specific_secret(monkeypatch):
    monkeypatch.setattr(main.settings, "affiliate_webhook_secret", SECRET)
    monkeypatch.setattr(main.settings, "affiliate_webhook_secrets", {" Example-Network ": NETWORK_SECRET})
    click = SimpleNamespace(click_id="click-network-secret", workspace_id="workspace-1")
    session, override = fake_session(click, None)
    main.app.dependency_overrides[get_session] = override
    body = json.dumps(
        {
            "event_id": "evt-network-secret",
            "click_id": "click-network-secret",
            "commission": "1.25",
            "revenue": "9.50",
            "status": "approved",
        },
        separators=(",", ":"),
    ).encode()
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/webhooks/conversions/Example-Network",
                content=body,
                headers=signed_headers(body, secret=NETWORK_SECRET),
            )
        assert response.status_code == 200
        assert response.json()["status"] == "recorded"
        added = [call.args[0] for call in session.add.call_args_list]
        row = next(value for value in added if isinstance(value, Conversion))
        ledger_entry = next(value for value in added if isinstance(value, ConversionLedgerEntry))
        assert row.network == "example-network"
        assert row.external_event_id == "evt-network-secret"
        assert ledger_entry.external_event_id == "evt-network-secret"
        assert ledger_entry.evidence_status == "signed_webhook_verified"
    finally:
        main.app.dependency_overrides.pop(get_session, None)
