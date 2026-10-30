from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main


def _override_user(monkeypatch, *, platform_admin: bool, workspace_id: str | None):
    async def current_user():
        return {
            "email": "provider-config-test@example.invalid",
            "user_id": "provider-config-test-user",
            "workspace_id": workspace_id,
            "workspace_role": "owner" if platform_admin else "admin",
            "is_admin": platform_admin,
        }
    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, current_user)


def test_global_provider_configuration_summaries_require_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(401, "Authentication required")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    with TestClient(main.app) as client:
        responses = [client.get("/api/integrations"), client.get("/api/capabilities")]

    assert [response.status_code for response in responses] == [401, 401]


def test_workspace_admin_cannot_read_global_provider_configuration(monkeypatch):
    _override_user(monkeypatch, platform_admin=False, workspace_id="tenant-workspace")
    calls = []

    def registry(config):
        calls.append("registry")
        return {"total": 0, "items": []}

    def capabilities(settings, registry_data):
        calls.append("capabilities")
        return {"items": []}

    monkeypatch.setattr(main, "build_network_registry", registry)
    monkeypatch.setattr(main, "build_capability_matrix", capabilities)
    with TestClient(main.app) as client:
        responses = [client.get("/api/integrations"), client.get("/api/capabilities")]

    assert [response.status_code for response in responses] == [403, 403]
    assert calls == []


def test_platform_admin_without_workspace_cannot_read_global_provider_configuration(monkeypatch):
    _override_user(monkeypatch, platform_admin=True, workspace_id=None)
    with TestClient(main.app) as client:
        responses = [client.get("/api/integrations"), client.get("/api/capabilities")]

    assert [response.status_code for response in responses] == [403, 403]


def test_platform_admin_can_read_configuration_status_without_exposing_secrets(monkeypatch, tmp_path):
    _override_user(monkeypatch, platform_admin=True, workspace_id="platform-operations")
    config_path = tmp_path / "integrations.yaml"
    config_path.write_text(
        "networks:\n"
        "  sentinel-provider:\n"
        "    adapter: generic_json\n"
        "    enabled: true\n"
        "    token: sentinel-provider-secret-value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(main.settings, "config_yaml_path", str(config_path))
    monkeypatch.setattr(main.settings, "openai_api_key", "sentinel-openai-secret-value")
    monkeypatch.setattr(main.settings, "reddit_access_token", "sentinel-reddit-secret-value")
    monkeypatch.setattr(main.settings, "pinterest_access_token", "sentinel-pinterest-secret-value")

    with TestClient(main.app) as client:
        registry = client.get("/api/integrations")
        capability = client.get("/api/capabilities")

    assert registry.status_code == 200, registry.text
    assert capability.status_code == 200, capability.text
    assert registry.json()["total"] == 1
    assert registry.json()["items"][0]["provider_id"] == "sentinel-provider"
    assert "required_configuration_present" in registry.json()["items"][0]
    for secret in (
        "sentinel-provider-secret-value",
        "sentinel-openai-secret-value",
        "sentinel-reddit-secret-value",
        "sentinel-pinterest-secret-value",
    ):
        assert secret not in registry.text
        assert secret not in capability.text
