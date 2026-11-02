from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session
from backend.models import AuditLog


OBSERVED_AT = datetime(2026, 10, 30, 10, 15, tzinfo=timezone.utc)
ADMIN_WORKSPACE = "audit-export-admin-workspace"


def _override_session(session):
    async def override_get_session():
        yield session
    return override_get_session


def _audit_row(*, actor: str = "operator@example.test"):
    return SimpleNamespace(
        id=42,
        created_at=OBSERVED_AT,
        workspace_id="customer-workspace-7",
        actor=actor,
        action="merchant.offer.reviewed",
        resource_type="merchant_offer",
        resource_id="offer-123",
        outcome="approved",
    )


def _client(session, user):
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: user
    return TestClient(main.app)


def _reset_overrides():
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)


def test_platform_audit_csv_export_is_filtered_formula_safe_and_audited():
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=Mock(return_value=[
            _audit_row(actor='=HYPERLINK("https://evil.invalid","open")')
        ]))),
        add=Mock(),
        commit=AsyncMock(),
    )
    user = {
        "user_id": "platform-admin-1",
        "email": "operator@example.test",
        "is_admin": True,
        "account_type": "platform_admin",
        "workspace_id": ADMIN_WORKSPACE,
        "workspace_role": "owner",
    }
    client = _client(db, user)
    try:
        response = client.get(
            "/api/admin/audit/export.csv"
            "?limit=250&workspace_id=customer-workspace-7"
            "&action=merchant.offer.reviewed&outcome=approved"
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["content-disposition"].startswith(
            'attachment; filename="omni-affiliate-platform-audit-'
        )
        assert response.headers["cache-control"] == "no-store, private"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"

        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 1
        exported = rows[0]
        assert exported["audit_id"] == "42"
        assert exported["workspace_id"] == "customer-workspace-7"
        assert exported["actor"].startswith("'=HYPERLINK(")
        assert exported["action"] == "merchant.offer.reviewed"
        assert exported["outcome"] == "approved"

        statement = db.scalars.await_args.args[0]
        compiled = statement.compile()
        assert "workspace_id" in str(statement)
        assert "action" in str(statement)
        assert "outcome" in str(statement)
        assert {"customer-workspace-7", "merchant.offer.reviewed", "approved"}.issubset(
            set(compiled.params.values())
        )

        db.commit.assert_awaited_once()
        audit = db.add.call_args.args[0]
        assert isinstance(audit, AuditLog)
        assert audit.workspace_id == ADMIN_WORKSPACE
        assert audit.actor == "operator@example.test"
        assert audit.action == "platform.audit.exported"
        assert audit.resource_type == "platform_audit_export"
        assert audit.outcome == "completed"
        assert audit.details_json == {
            "format": "csv",
            "row_count": 1,
            "row_limit": 250,
            "workspace_filter_applied": True,
            "action_filter_applied": True,
            "outcome_filter_applied": True,
            "exported_audit_values_recorded": False,
        }
    finally:
        client.close()
        _reset_overrides()


def test_platform_audit_csv_export_requires_an_explicit_platform_admin():
    db = SimpleNamespace(
        scalars=AsyncMock(),
        add=Mock(),
        commit=AsyncMock(),
    )
    client = _client(db, {
        "user_id": "merchant-user",
        "email": "merchant@example.test",
        "is_admin": False,
        "account_type": "merchant_product_owner",
        "workspace_id": ADMIN_WORKSPACE,
        "workspace_role": "owner",
    })
    try:
        response = client.get("/api/admin/audit/export.csv")
        assert response.status_code == 403
        assert "Platform Super Admin" in response.text
        db.scalars.assert_not_awaited()
        db.add.assert_not_called()
        db.commit.assert_not_awaited()
    finally:
        client.close()
        _reset_overrides()


def test_platform_audit_csv_export_fails_closed_without_an_audit_workspace():
    db = SimpleNamespace(
        scalars=AsyncMock(),
        add=Mock(),
        commit=AsyncMock(),
    )
    client = _client(db, {
        "user_id": "platform-admin-1",
        "email": "operator@example.test",
        "is_admin": True,
        "account_type": "platform_admin",
        "workspace_id": None,
        "workspace_role": "owner",
    })
    try:
        response = client.get("/api/admin/audit/export.csv")
        assert response.status_code == 403
        assert "anchor the platform audit-export record" in response.text
        db.scalars.assert_not_awaited()
        db.add.assert_not_called()
        db.commit.assert_not_awaited()
    finally:
        client.close()
        _reset_overrides()
