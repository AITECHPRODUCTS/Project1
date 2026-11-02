from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main


_THRESHOLD = {"network": "Example Affiliate", "currency": "USD", "minimum_threshold": 100.0, "reported_balance": 25.0}
_FUNDS_RECEIVED = {"funds_received_at": "2026-10-25T10:00:00Z", "reconciliation_note": "Reviewed by operator"}


def _protected_requests(client: TestClient):
    return [
        client.get("/api/finance/thresholds"),
        client.post("/api/finance/thresholds", json=_THRESHOLD),
        client.post("/api/finance/thresholds/threshold-1/funds-received", json=_FUNDS_RECEIVED),
        client.get("/api/finance/mail-commissions"),
        client.get("/api/leads"),
        client.get("/api/email/queue"),
        client.post("/api/email/worker/run"),
        client.get("/api/audit"),
    ]


def test_finance_lead_queue_and_audit_routes_require_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(status_code=401, detail="Authentication required")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    with TestClient(main.app) as client:
        responses = _protected_requests(client)
    assert [response.status_code for response in responses] == [401] * len(responses)


def test_finance_lead_queue_and_audit_routes_require_active_workspace(monkeypatch):
    async def owner_without_workspace():
        return {
            "email": "owner@example.invalid",
            "is_admin": True,
            "user_id": "test-owner",
            "workspace_id": None,
            "workspace_role": "owner",
        }

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, owner_without_workspace)
    with TestClient(main.app) as client:
        responses = _protected_requests(client)
    assert [response.status_code for response in responses] == [403] * len(responses)
