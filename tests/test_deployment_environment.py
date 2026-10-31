from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_passes_workspace_scoped_signed_ad_collector_secrets_to_api():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    api_environment = compose["services"]["api"]["environment"]

    assert api_environment["AD_PERFORMANCE_WEBHOOK_SECRETS"] == "${AD_PERFORMANCE_WEBHOOK_SECRETS:-}"


def test_env_example_documents_signed_ad_collector_map_without_committing_secrets():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    matches = [line for line in lines if line.startswith("AD_PERFORMANCE_WEBHOOK_SECRETS=")]

    assert matches == ["AD_PERFORMANCE_WEBHOOK_SECRETS={}"]
    assert any("workspace UUID" in line and "trusted-collector secret" in line for line in lines)
