from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main


def _override_auth(monkeypatch, user: dict):
    async def authenticated_user():
        return user

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, authenticated_user)


def test_knowledge_ingestion_is_restricted_to_platform_super_admin(monkeypatch):
    _override_auth(monkeypatch, {
        "email": "owner@example.invalid",
        "user_id": "workspace-owner",
        "workspace_id": "owner-workspace",
        "workspace_role": "owner",
        "is_admin": False,
    })

    with TestClient(main.app) as client:
        response = client.post("/api/knowledge/ingest")

    assert response.status_code == 403
    assert "Platform Super Admin" in response.text


def test_platform_super_admin_can_trigger_knowledge_ingestion(monkeypatch):
    _override_auth(monkeypatch, {
        "email": "platform-admin@example.invalid",
        "user_id": "platform-admin",
        "workspace_id": "platform-operations",
        "workspace_role": "member",
        "is_admin": True,
    })
    monkeypatch.setattr(main, "ingest_doctrine", lambda *args, **kwargs: {"documents": 5, "chunks": 12})

    with TestClient(main.app) as client:
        response = client.post("/api/knowledge/ingest")

    assert response.status_code == 200
    assert response.json()["status"] == "indexed"
    assert response.json()["documents"] == 5
    assert response.json()["chunks"] == 12


async def test_knowledge_status_does_not_disclose_absolute_storage_path():
    result = await main.knowledge_status()

    assert "path" not in result
    assert result["storage_configured"] is True
    assert result["collection"] == "affiliate_doctrine"
