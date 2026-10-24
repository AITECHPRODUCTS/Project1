from backend.config import Settings
from backend.services.capability_matrix import CAPABILITY_STATUSES, build_capability_matrix
from backend.services.integration_registry import build_network_registry


def test_capability_matrix_uses_only_documented_statuses():
    settings = Settings(_env_file=None, app_env="development")
    registry = build_network_registry(
        {"networks": {
            "openaffiliate": {"enabled": True, "adapter": "openaffiliate"},
            "clickbank": {"enabled": False, "adapter": "clickbank"},
        }},
        environ={},
    )
    matrix = build_capability_matrix(settings, registry)
    assert all(item["status"] in CAPABILITY_STATUSES for item in matrix["items"])
    assert matrix["counts"]["manual_provider_flow"] >= 2
    assert matrix["counts"]["not_supported"] >= 1


def test_capability_matrix_never_claims_provider_write_access_from_config():
    settings = Settings(_env_file=None, app_env="development")
    registry = build_network_registry(
        {"networks": {"amazon_associates": {"enabled": True, "adapter": "signed_proxy"}}},
        environ={"AMAZON_ASSOCIATES_SIGNED_PROXY_ENDPOINT": "https://api.example.test",
                 "AMAZON_ASSOCIATES_PROXY_TOKEN": "configured-but-not-proven"},
    )
    matrix = build_capability_matrix(settings, registry)
    provider = matrix["provider_items"][0]
    assert provider["registry_status"] == "configured_not_health_checked"
    assert provider["status"] == "not_configured"
    assert provider["external_side_effect"] is False
