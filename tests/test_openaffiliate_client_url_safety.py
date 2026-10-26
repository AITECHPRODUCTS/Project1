from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from backend.tools.affiliate_api import OpenAffiliateClient


@pytest.mark.asyncio
async def test_openaffiliate_client_uses_pinned_public_fetch_boundary(monkeypatch):
    calls: list[tuple[str, dict[str, Any]]] = []

    @asynccontextmanager
    async def reject_private(url: str, **kwargs):
        calls.append((url, kwargs))
        raise ValueError("Private, loopback, link-local, multicast or reserved destinations are blocked")
        yield  # pragma: no cover

    monkeypatch.setattr("backend.tools.affiliate_api.open_public_http_response", reject_private)
    client = OpenAffiliateClient(base_url="https://127.0.0.1/api")

    with pytest.raises(ValueError, match="Private"):
        await client.fetch_programs(q="creator tools", limit=10)

    assert calls == [(
        "https://127.0.0.1/api/programs",
        {
            "method": "GET",
            "params": {"limit": 10, "q": "creator tools"},
            "headers": {"Accept": "application/json", "User-Agent": "AffiliateOS/0.1"},
            "timeout": 10.0,
        },
    )]


@pytest.mark.asyncio
async def test_openaffiliate_client_caps_decoded_response_and_keeps_redirects_off(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        headers = {
            "content-type": "application/json",
            "content-length": "51",
        }

        def raise_for_status(self):
            return None

    @asynccontextmanager
    async def fake_open(url: str, **kwargs):
        calls.append((url, kwargs))
        yield Response()

    async def fake_read(response, *, max_bytes, raw=False):
        assert max_bytes == 5 * 1024 * 1024
        assert raw is False
        return b'{"data":[{"id":"program-1","name":"Example program"}],"count":1}'

    monkeypatch.setattr("backend.tools.affiliate_api.open_public_http_response", fake_open)
    monkeypatch.setattr("backend.tools.affiliate_api.read_limited_response", fake_read)
    client = OpenAffiliateClient(base_url="https://provider.example/api")

    result = await client.fetch_programs(q="creator tools", limit=5)

    assert calls == [(
        "https://provider.example/api/programs",
        {
            "method": "GET",
            "params": {"limit": 5, "q": "creator tools"},
            "headers": {"Accept": "application/json", "User-Agent": "AffiliateOS/0.1"},
            "timeout": 10.0,
        },
    )]
    assert result["data"][0]["name"] == "Example program"
