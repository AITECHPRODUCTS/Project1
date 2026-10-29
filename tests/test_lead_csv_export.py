from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from backend import main
from backend.database import get_session
from backend.models import AuditLog


WORKSPACE_ID = "lead-export-workspace"
OBSERVED_AT = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


def _override_session(session):
    async def override_get_session():
        yield session
    return override_get_session


def _lead(*, unsafe_resource: str = "Creator guide"):
    return SimpleNamespace(
        id="lead-export-1",
        workspace_id=WORKSPACE_ID,
        email="reader@example.invalid",
        lead_magnet=unsafe_resource,
        consent_at=OBSERVED_AT,
        email_consent_confirmed_at=OBSERVED_AT,
        consent_source="persisted_landing_page",
        unsubscribed_at=None,
        purchased_at=None,
        metadata_json={
            "attribution": {
                "first_touch": {"utm_source": "newsletter", "utm_campaign": "launch"},
                "last_touch": {"utm_source": "social", "utm_campaign": "autumn"},
                "last_touch_at": OBSERVED_AT.isoformat(),
            }
        },
        created_at=OBSERVED_AT,
    )


def _client(session, user):
    main.app.dependency_overrides[get_session] = _override_session(session)
    main.app.dependency_overrides[main.require_auth] = lambda: user
    return TestClient(main.app)


def _reset_overrides():
    main.app.dependency_overrides.pop(get_session, None)
    main.app.dependency_overrides.pop(main.require_auth, None)


def test_lead_csv_export_is_workspace_scoped_audited_and_formula_safe():
    row = _lead(unsafe_resource='=HYPERLINK("https://evil.invalid","open")')
    rows_result = SimpleNamespace(all=Mock(return_value=[row]))
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=1),
        scalars=AsyncMock(return_value=rows_result),
        add=Mock(),
        commit=AsyncMock(),
    )
    client = _client(db, {
        "user_id": "user-1", "workspace_id": WORKSPACE_ID, "email": "exporter@example.invalid"
    })
    try:
        response = client.get("/api/leads/export.csv?search=newsletter")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["content-disposition"].startswith('attachment; filename="omni-affiliate-leads-')
        assert response.headers["cache-control"] == "no-store, private"
        assert response.headers["x-content-type-options"] == "nosniff"

        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 1
        exported = rows[0]
        assert exported["lead_id"] == "lead-export-1"
        assert exported["email"] == "reader@example.invalid"
        assert exported["first_touch_utm_source"] == "newsletter"
        assert exported["first_touch_utm_campaign"] == "launch"
        assert exported["last_touch_utm_source"] == "social"
        assert exported["last_touch_utm_campaign"] == "autumn"
        assert exported["last_touch_at"] == OBSERVED_AT.isoformat()
        assert exported["unsubscribed"] == "false"
        assert exported["purchased"] == "false"
        assert exported["lead_magnet"].startswith("'=HYPERLINK(")

        count_query = db.scalar.await_args.args[0]
        export_query = db.scalars.await_args.args[0]
        for statement in (count_query, export_query):
            compiled = statement.compile()
            assert "workspace_id" in str(statement)
            assert WORKSPACE_ID in compiled.params.values()
            assert "%newsletter%" in compiled.params.values()

        db.commit.assert_awaited_once()
        audit = db.add.call_args.args[0]
        assert isinstance(audit, AuditLog)
        assert audit.workspace_id == WORKSPACE_ID
        assert audit.actor == "exporter@example.invalid"
        assert audit.action == "leads.export_csv"
        assert audit.outcome == "completed"
        assert audit.details_json == {
            "format": "csv",
            "matching_rows": 1,
            "row_limit": main.MAX_LEAD_EXPORT_ROWS,
            "search_supplied": True,
            "search_value_recorded": False,
            "lead_values_recorded": False,
        }
        assert "newsletter" not in json.dumps(audit.details_json)
        assert "reader@example.invalid" not in json.dumps(audit.details_json)
    finally:
        client.close()
        _reset_overrides()


def test_lead_csv_export_rejects_missing_workspace_before_querying():
    db = SimpleNamespace(
        scalar=AsyncMock(),
        scalars=AsyncMock(),
        add=Mock(),
        commit=AsyncMock(),
    )
    client = _client(db, {"user_id": "user-1", "workspace_id": None, "email": "reader@example.invalid"})
    try:
        response = client.get("/api/leads/export.csv")
        assert response.status_code == 403
        db.scalar.assert_not_awaited()
        db.scalars.assert_not_awaited()
        db.add.assert_not_called()
    finally:
        client.close()
        _reset_overrides()


def test_lead_csv_export_refuses_oversized_result_instead_of_truncating():
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=main.MAX_LEAD_EXPORT_ROWS + 1),
        scalars=AsyncMock(),
        add=Mock(),
        commit=AsyncMock(),
    )
    client = _client(db, {"user_id": "user-1", "workspace_id": WORKSPACE_ID, "email": "exporter@example.invalid"})
    try:
        response = client.get("/api/leads/export.csv")
        assert response.status_code == 413
        assert "Narrow the global search and retry" in response.json()["detail"]
        db.scalars.assert_not_awaited()
        db.commit.assert_awaited_once()
        audit = db.add.call_args.args[0]
        assert isinstance(audit, AuditLog)
        assert audit.action == "leads.export_csv"
        assert audit.outcome == "rejected_row_limit"
        assert audit.details_json["matching_rows"] == main.MAX_LEAD_EXPORT_ROWS + 1
        assert audit.details_json["lead_values_recorded"] is False
    finally:
        client.close()
        _reset_overrides()
