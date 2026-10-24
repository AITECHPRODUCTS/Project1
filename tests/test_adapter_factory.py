from __future__ import annotations

from typing import Any

import pytest

from backend.adapters.factory import ConfiguredJSONAdapter


@pytest.mark.asyncio
async def test_configured_json_adapter_rejects_private_endpoint_before_opening_http_client(monkeypatch):
    endpoint = "https://127.0.0.1/private"
    calls: list[str] = []

    async def reject_private(url: str) -> str:
        calls.append(url)
        raise ValueError("Private, loopback, link-local, multicast or reserved destinations are blocked")

    def unexpected_client(**kwargs: Any):
        raise AssertionError("HTTP client must not be created before URL validation succeeds")

    monkeypatch.setattr("backend.adapters.factory.validate_public_http_url", reject_private)
    monkeypatch.setattr("backend.adapters.factory.httpx.AsyncClient", unexpected_client)
    adapter = ConfiguredJSONAdapter("test-network", endpoint, "test-token")

    with pytest.raises(ValueError, match="Private"):
        await adapter.fetch_offers(query="tools", limit=10)
    assert calls == [endpoint]


@pytest.mark.asyncio
async def test_configured_json_adapter_bounds_limit_and_normalizes_items(monkeypatch):
    endpoint = "https://partner.example/api/offers"
    monkeypatch.setattr(
        "backend.adapters.factory.validate_public_http_url",
        lambda url: _async_value(url),
    )
    captured: dict[str, Any] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"data": [{"id": str(i)} for i in range(5)] + ["not-an-object"]}

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, url: str, *, params: dict[str, Any], headers: dict[str, str]):
            captured.update({"url": url, "params": params, "headers": headers})
            return Response()

    monkeypatch.setattr("backend.adapters.factory.httpx.AsyncClient", Client)
    adapter = ConfiguredJSONAdapter("test-network", endpoint, "test-token")
    result = await adapter.fetch_offers(query="creator tools", limit=-10)

    assert captured["url"] == endpoint
    assert captured["params"] == {"q": "creator tools", "limit": 1}
    assert len(result) == 1
    assert result[0] == {"id": "0"}


async def _async_value(value: str) -> str:
    return value
