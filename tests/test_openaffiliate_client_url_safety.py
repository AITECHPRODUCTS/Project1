from __future__ import annotations

from typing import Any

import pytest

from backend.tools.affiliate_api import OpenAffiliateClient


@pytest.mark.asyncio
async def test_openaffiliate_client_rejects_private_base_url_before_opening_http_client(monkeypatch):
    calls: list[str] = []

    async def reject_private(url: str) -> str:
        calls.append(url)
        raise ValueError("Private, loopback, link-local, multicast or reserved destinations are blocked")

    def unexpected_client(**kwargs: Any):
        raise AssertionError("HTTP client must not open before the OpenAffiliate URL is validated")

    monkeypatch.setattr("backend.tools.affiliate_api.validate_public_http_url", reject_private)
    monkeypatch.setattr("backend.tools.affiliate_api.httpx.AsyncClient", unexpected_client)
    client = OpenAffiliateClient(base_url="https://127.0.0.1/api")

    with pytest.raises(ValueError, match="Private"):
        await client.fetch_programs(q="creator tools", limit=10)

    assert calls == ["https://127.0.0.1/api/programs"]


@pytest.mark.asyncio
async def test_openaffiliate_client_validates_provider_url_and_keeps_redirects_disabled(monkeypatch):
    validated: list[str] = []
    request: dict[str, Any] = {}

    async def allow_test_host(url: str) -> str:
        validated.append(url)
        return url

    class Response:
        headers = {"content-length": "51"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b'{"data":[{"id":"program-1","name":"Example program"}],"count":1}'

    class Stream:
        async def __aenter__(self):
            return Response()

        async def __aexit__(self, *args: Any):
            return None

    class Client:
        def __init__(self, **kwargs: Any):
            request["client_options"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: Any):
            return None

        def stream(self, method: str, url: str, *, params: dict[str, Any]):
            request.update({"method": method, "url": url, "params": params})
            return Stream()

    monkeypatch.setattr("backend.tools.affiliate_api.validate_public_http_url", allow_test_host)
    monkeypatch.setattr("backend.tools.affiliate_api.httpx.AsyncClient", Client)
    client = OpenAffiliateClient(base_url="https://provider.example/api")

    result = await client.fetch_programs(q="creator tools", limit=5)

    assert validated == ["https://provider.example/api/programs"]
    assert request["method"] == "GET"
    assert request["url"] == validated[0]
    assert request["params"] == {"limit": 5, "q": "creator tools"}
    assert request["client_options"]["follow_redirects"] is False
    assert result["data"][0]["name"] == "Example program"
