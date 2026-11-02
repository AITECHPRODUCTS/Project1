from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main


def test_commission_email_import_is_bound_to_active_workspace(monkeypatch):
    called = {}

    async def fake_import(**kwargs):
        called.update(kwargs)
        return {"messages_matched": 2, "rows_created": 1}

    monkeypatch.setattr(
        "backend.services.commission_mail_importer.import_commission_emails",
        fake_import,
    )
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "is_admin": True,
        "user_id": "user-1",
        "workspace_id": "workspace-1",
        "workspace_role": "owner",
    }
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/finance/email-import")

        assert response.status_code == 200
        assert response.json()["rows_created"] == 1
        assert called["workspace_id"] == "workspace-1"
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)


def test_commission_email_import_rejects_missing_workspace_before_import(monkeypatch):
    called = {"value": False}

    async def fake_import(**kwargs):
        called["value"] = True
        return {}

    monkeypatch.setattr(
        "backend.services.commission_mail_importer.import_commission_emails",
        fake_import,
    )
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "is_admin": True,
        "user_id": "user-1",
        "workspace_id": None,
        "workspace_role": "owner",
    }
    try:
        with TestClient(main.app) as client:
            response = client.post("/api/finance/email-import")

        assert response.status_code == 403
        assert called["value"] is False
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)
