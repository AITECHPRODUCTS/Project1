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
    assert matrix["counts"]["partially_available"] >= 0


def test_capability_matrix_never_claims_provider_write_access_from_config():
    settings = Settings(_env_file=None, app_env="development")
    registry = build_network_registry(
        {"networks": {"amazon_associates": {"enabled": True, "adapter": "signed_proxy"}}},
        environ={
            "AMAZON_ASSOCIATES_SIGNED_PROXY_ENDPOINT": "https://api.example.test",
            "AMAZON_ASSOCIATES_PROXY_TOKEN": "configured-but-not-proven",
        },
    )
    matrix = build_capability_matrix(settings, registry)
    provider = matrix["provider_items"][0]
    assert provider["registry_status"] == "configured_not_health_checked"
    assert provider["status"] == "partially_available"
    assert provider["external_side_effect"] is False


def test_capability_matrix_reports_existing_super_admin_foundations_as_partial():
    settings = Settings(_env_file=None, app_env="development")
    matrix = build_capability_matrix(settings, {"items": []})
    admin = next(item for item in matrix["items"] if item["id"] == "super_admin_operations")

    assert admin["status"] == "partially_available"
    assert "tenant suspend/reinstate" in admin["reason"]
    assert "dead-letter recovery" in admin["reason"]
    assert admin["external_side_effect"] is False


def test_capability_matrix_distinguishes_configured_offer_adapter_from_verified_offer_data():
    settings = Settings(_env_file=None, app_env="development")
    matrix = build_capability_matrix(
        settings,
        {"items": [{
            "provider_id": "openaffiliate",
            "status": "configured_not_health_checked",
            "adapter": "openaffiliate",
            "reason": "Configured, not health checked",
        }]},
    )

    offer = next(item for item in matrix["items"] if item["id"] == "offer_discovery")
    provider = next(item for item in matrix["provider_items"] if item["provider_id"] == "openaffiliate")

    assert offer["status"] == "partially_available"
    assert "not passed a live health/contract check" in offer["reason"]
    assert provider["status"] == "partially_available"
    assert provider["external_side_effect"] is False


def test_workspace_credentialed_readonly_provider_is_partial_until_connected():
    settings = Settings(_env_file=None, app_env="development")
    registry = build_network_registry(
        {"networks": {"digistore24": {"enabled": True, "adapter": "workspace_read_only"}}},
        environ={},
    )
    provider = registry["items"][0]
    assert provider["status"] == "not_configured"
    assert provider["adapter_coverage"] == "workspace_credentialed_read_only"
    assert provider["credential_scope"] == "workspace"
    assert provider["offer_discovery"] is True
    assert provider["commission_reporting"] is False
    assert provider["publish_content"] is False
    matrix = build_capability_matrix(settings, registry)
    assert all(item["status"] in CAPABILITY_STATUSES for item in matrix["items"])
