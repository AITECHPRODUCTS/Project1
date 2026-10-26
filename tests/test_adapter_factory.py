from __future__ import annotations

from typing import Any

import pytest

from backend.adapters.factory import ConfiguredJSONAdapter


@pytest.mark.asyncio
async def test_configured_json_adapter_rejects_private_endpoint_before_network_io():
    adapter = ConfiguredJSONAdapter(
        "test-network",
        "https://127.0.0.1/private",
        "test-token",
    )

    # The real pinned helper rejects loopback while resolving the destination,
    # before it constructs or opens an HTTP client.
    with pytest.raises(ValueError, match="Private"):
        await adapter.fetch_offers(query="tools", limit=10)


@pytest.mark.asyncio
async def test_configured_json_adapter_uses_pinned_helper_and_normalizes_items(monkeypatch):
    endpoint = "https://partner.example/api/offers"
    captured: dict[str, Any] = {}

    async def fake_request_public_json(url: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"url": url, **kwargs})
        return {"data": [{"id": str(i)} for i in range(5)] + ["not-an-object"]}

    monkeypatch.setattr(
        "backend.adapters.factory.request_public_json",
        fake_request_public_json,
    )
    adapter = ConfiguredJSONAdapter("test-network", endpoint, "test-token")
    result = await adapter.fetch_offers(query="creator tools", limit=-10)

    assert captured == {
        "url": endpoint,
        "method": "GET",
        "params": {"q": "creator tools", "limit": 1},
        "headers": {
            "Authorization": "Bearer test-token",
            "Accept": "application/json",
        },
        "timeout": 20,
        "max_bytes": 2_000_000,
    }
    assert result == [{"id": "0"}]
