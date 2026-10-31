from __future__ import annotations

from pathlib import Path
import re

import pytest
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


async def _run_proxy_headers(
    *,
    peer: tuple[str, int],
    trusted_hosts: str,
    headers: list[tuple[bytes, bytes]],
    scheme: str = "http",
) -> dict[str, object]:
    observed: dict[str, object] = {}

    async def app(scope, receive, send):
        observed["client"] = scope.get("client")
        observed["scheme"] = scope.get("scheme")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        return None

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": "/health",
        "raw_path": b"/health",
        "query_string": b"",
        "headers": headers,
        "client": peer,
        "server": ("staging.example.invalid", 443),
    }
    middleware = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    await middleware(scope, receive, send)
    return observed


@pytest.mark.asyncio
async def test_untrusted_peer_cannot_spoof_forwarded_client_or_scheme():
    original_peer = ("198.51.100.24", 51340)
    observed = await _run_proxy_headers(
        peer=original_peer,
        trusted_hosts="192.0.2.0/24",
        headers=[
            (b"x-forwarded-for", b"203.0.113.88"),
            (b"x-forwarded-proto", b"https"),
        ],
    )
    assert observed["client"] == original_peer
    assert observed["scheme"] == "http"


@pytest.mark.asyncio
async def test_trusted_cidr_peer_can_supply_forwarded_client_and_https_scheme():
    observed = await _run_proxy_headers(
        peer=("192.0.2.14", 44321),
        trusted_hosts="192.0.2.0/24",
        headers=[
            (b"x-forwarded-for", b"203.0.113.18"),
            (b"x-forwarded-proto", b"https"),
        ],
    )
    assert observed["client"] == ("203.0.113.18", 0)
    assert observed["scheme"] == "https"


@pytest.mark.asyncio
async def test_trusted_proxy_chain_selects_first_untrusted_forwarded_address():
    observed = await _run_proxy_headers(
        peer=("192.0.2.14", 44321),
        trusted_hosts="192.0.2.0/24,198.51.100.0/24",
        headers=[
            (b"x-forwarded-for", b"203.0.113.42, 198.51.100.9"),
            (b"x-forwarded-proto", b"https"),
        ],
    )
    assert observed["client"] == ("203.0.113.42", 0)
    assert observed["scheme"] == "https"


def test_runtime_requirement_guarantees_uvicorn_cidr_support():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"(?m)^uvicorn\[standard\]>=0\.31,<1\.0\s*$", requirements)
