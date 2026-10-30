from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config import Settings


@pytest.mark.parametrize(
    "allowed",
    [
        "127.0.0.1",
        "::1",
        "127.0.0.1,10.24.0.7/32",
        "10.24.0.0/24",
        "2001:db8:abcd::/48",
    ],
)
def test_forwarded_allow_ips_accepts_explicit_addresses_and_cidrs(allowed: str):
    settings = Settings(_env_file=None, forwarded_allow_ips=allowed)
    assert settings.forwarded_allow_ips == ",".join(part.strip() for part in allowed.split(","))


@pytest.mark.parametrize(
    "forbidden",
    ["*", "0.0.0.0/0", "::/0", "proxy.internal", "", "127.0.0.1,*"],
)
def test_forwarded_allow_ips_rejects_wildcards_default_routes_hostnames_and_empty(forbidden: str):
    with pytest.raises(ValidationError, match="FORWARDED_ALLOW_IPS"):
        Settings(_env_file=None, forwarded_allow_ips=forbidden)


def test_compose_passes_forwarded_allow_ips_with_loopback_safe_default():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "FORWARDED_ALLOW_IPS: ${FORWARDED_ALLOW_IPS:-127.0.0.1}" in compose
    assert "FORWARDED_ALLOW_IPS: ${FORWARDED_ALLOW_IPS:-*}" not in compose


def test_env_example_documents_loopback_only_trusted_proxy_default():
    example = Path(".env.example").read_text(encoding="utf-8")
    assert "FORWARDED_ALLOW_IPS=127.0.0.1" in example
    assert "Do not set to *" in example
