from __future__ import annotations

import httpx
import pytest

from backend.services import url_safety


@pytest.mark.asyncio
async def test_sdk_transport_pins_connection_and_preserves_host_and_tls_sni(monkeypatch):
    original_url = httpx.URL("https://llm-provider.example/v1/chat/completions")
    resolved: list[str] = []
    observed: dict[str, str | None] = {}

    async def resolve(url: str):
        resolved.append(url)
        return original_url, "llm-provider.example", "93.184.216.34"

    async def handle(request: httpx.Request) -> httpx.Response:
        observed["scheme"] = request.url.scheme
        observed["connect_host"] = request.url.host
        observed["host_header"] = request.headers.get("host")
        observed["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, json={"id": "test-response"}, request=request)

    monkeypatch.setattr(url_safety, "_resolve_public_target", resolve)
    inner = httpx.MockTransport(handle)
    transport = url_safety.PinnedPublicAsyncTransport(inner_transport=inner)
    request = httpx.Request("POST", str(original_url), json={"model": "test-model"})

    response = await transport.handle_async_request(request)
    try:
        assert resolved == [str(original_url)]
        assert observed == {
            "scheme": "https",
            "connect_host": "93.184.216.34",
            "host_header": "llm-provider.example",
            "sni": "llm-provider.example",
        }
        assert str(response.request.url) == str(original_url)
        assert response.json() == {"id": "test-response"}
    finally:
        await response.aclose()
        await transport.aclose()


@pytest.mark.asyncio
async def test_sdk_transport_rejects_plain_http_before_resolving(monkeypatch):
    called = False

    async def resolve(url: str):
        nonlocal called
        called = True
        raise AssertionError("HTTP URLs must be rejected before DNS resolution")

    monkeypatch.setattr(url_safety, "_resolve_public_target", resolve)
    transport = url_safety.PinnedPublicAsyncTransport(inner_transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    try:
        request = httpx.Request("POST", "http://llm-provider.example/v1/chat/completions", json={"x": 1})
        with pytest.raises(ValueError, match="require HTTPS"):
            await transport.handle_async_request(request)
        assert called is False
    finally:
        await transport.aclose()


@pytest.mark.asyncio
async def test_pinned_sdk_client_disables_redirects_and_ambient_proxies():
    async with url_safety.pinned_public_async_client(timeout=9.0) as client:
        assert isinstance(client._transport, url_safety.PinnedPublicAsyncTransport)
        assert client.follow_redirects is False
        assert client.trust_env is False
        assert client.timeout.connect <= 4.0


def test_sync_sdk_transport_pins_connection_and_preserves_host_and_tls_sni(monkeypatch):
    original_url = httpx.URL("https://llm-provider.example/v1/chat/completions")
    resolved: list[str] = []
    observed: dict[str, str | None] = {}

    def resolve(url: str):
        resolved.append(url)
        return original_url, "llm-provider.example", "93.184.216.34"

    def handle(request: httpx.Request) -> httpx.Response:
        observed["scheme"] = request.url.scheme
        observed["connect_host"] = request.url.host
        observed["host_header"] = request.headers.get("host")
        observed["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, json={"id": "sync-test-response"}, request=request)

    monkeypatch.setattr(url_safety, "_resolve_public_target_sync", resolve)
    transport = url_safety.PinnedPublicSyncTransport(inner_transport=httpx.MockTransport(handle))
    request = httpx.Request("POST", str(original_url), json={"model": "test-model"})

    response = transport.handle_request(request)
    try:
        assert resolved == [str(original_url)]
        assert observed == {
            "scheme": "https",
            "connect_host": "93.184.216.34",
            "host_header": "llm-provider.example",
            "sni": "llm-provider.example",
        }
        assert str(response.request.url) == str(original_url)
        assert response.json() == {"id": "sync-test-response"}
    finally:
        response.close()
        transport.close()


def test_sync_sdk_transport_rejects_plain_http_before_resolving(monkeypatch):
    called = False

    def resolve(url: str):
        nonlocal called
        called = True
        raise AssertionError("HTTP URLs must be rejected before DNS resolution")

    monkeypatch.setattr(url_safety, "_resolve_public_target_sync", resolve)
    transport = url_safety.PinnedPublicSyncTransport(inner_transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    try:
        request = httpx.Request("POST", "http://llm-provider.example/v1/chat/completions", json={"x": 1})
        with pytest.raises(ValueError, match="require HTTPS"):
            transport.handle_request(request)
        assert called is False
    finally:
        transport.close()
