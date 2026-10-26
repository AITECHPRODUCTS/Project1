from __future__ import annotations

import json
import socket
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main
from backend.services import url_safety, video_engine
from backend.tenancy import get_workspace_id


def _dns_answer(ip: str, port: int = 443):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    address = (ip, port, 0, 0) if family == socket.AF_INET6 else (ip, port)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", address)]


@pytest.mark.asyncio
async def test_public_url_validation_rejects_mixed_public_and_private_dns(monkeypatch):
    def mixed_answers(host, port, *args, **kwargs):
        return _dns_answer("93.184.216.34", port) + _dns_answer("127.0.0.1", port)

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", mixed_answers)
    with pytest.raises(ValueError, match="Private"):
        await url_safety.validate_public_http_url("https://rebinding.example/path")


@pytest.mark.asyncio
async def test_public_request_pins_ip_and_preserves_host_sni_without_proxy_env(monkeypatch):
    captured: dict[str, Any] = {}

    def public_answer(host, port, *args, **kwargs):
        return _dns_answer("93.184.216.34", port)

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/plain", "content-length": "2"}

        async def aclose(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_options"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def build_request(self, method, url, *, params=None, headers=None, json=None):
            return httpx.Request(method, url, params=params, headers=headers, json=json)

        async def send(self, request, *, stream=False):
            captured["request_url"] = str(request.url)
            captured["host_header"] = request.headers.get("host")
            captured["sni_hostname"] = request.extensions.get("sni_hostname")
            captured["stream"] = stream
            return FakeResponse()

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", public_answer)
    monkeypatch.setattr(url_safety.httpx, "AsyncClient", FakeClient)
    async with url_safety.open_public_http_response(
        "https://rebinding.example:8443/path?q=1",
        headers={"Accept": "text/plain"},
        timeout=3,
    ) as response:
        assert response.status_code == 200

    assert captured["request_url"] == "https://93.184.216.34:8443/path?q=1"
    assert captured["host_header"] == "rebinding.example:8443"
    assert captured["sni_hostname"] == "rebinding.example"
    assert captured["stream"] is True
    assert captured["client_options"]["follow_redirects"] is False
    assert captured["client_options"]["trust_env"] is False


@pytest.mark.asyncio
async def test_public_page_rejects_redirects_instead_of_following_them(monkeypatch):
    class FakeResponse:
        status_code = 302
        headers = {"location": "http://127.0.0.1/admin", "content-length": "0"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            if False:
                yield b""

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        yield FakeResponse()

    monkeypatch.setattr(url_safety, "open_public_http_response", fake_open)
    with pytest.raises(ValueError, match="Redirect not followed"):
        await url_safety.fetch_public_page("https://safe.example/page")


@pytest.mark.asyncio
async def test_public_page_enforces_declared_and_streamed_response_byte_limits(monkeypatch):
    class TooLargeDeclared:
        status_code = 200
        headers = {"content-type": "text/html", "content-length": "11"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"x"

    @asynccontextmanager
    async def declared_open(url, **kwargs):
        yield TooLargeDeclared()

    monkeypatch.setattr(url_safety, "open_public_http_response", declared_open)
    with pytest.raises(ValueError, match="byte limit"):
        await url_safety.fetch_public_page("https://safe.example/page", max_bytes=10)

    class TooLargeStream:
        status_code = 200
        headers = {"content-type": "text/html", "content-length": "1"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"x" * 11

    @asynccontextmanager
    async def streamed_open(url, **kwargs):
        yield TooLargeStream()

    monkeypatch.setattr(url_safety, "open_public_http_response", streamed_open)
    with pytest.raises(ValueError, match="byte limit"):
        await url_safety.fetch_public_page("https://safe.example/page", max_bytes=10)


@pytest.mark.asyncio
async def test_public_page_rejects_non_text_content_types(monkeypatch):
    class ImageResponse:
        status_code = 200
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"image"

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        yield ImageResponse()

    monkeypatch.setattr(url_safety, "open_public_http_response", fake_open)
    with pytest.raises(ValueError, match="Unsupported content type"):
        await url_safety.fetch_public_page("https://safe.example/image")


@pytest.mark.asyncio
async def test_pexels_rejects_redirects_and_oversized_assets_before_writing(monkeypatch, tmp_path):
    monkeypatch.setattr(video_engine, "get_settings", lambda: SimpleNamespace(pexels_api_key="test-api-key"))
    monkeypatch.setattr(video_engine, "MAX_BROLL_DOWNLOAD_BYTES", 8)
    payload = {"videos": [{
        "id": 1, "url": "https://www.pexels.com/video/1/", "duration": 30,
        "video_files": [{
            "file_type": "video/mp4", "link": "https://videos.example/video.mp4",
            "width": 1080, "height": 1920, "size": 5,
        }],
    }]}

    class APIResponse:
        status_code = 200
        headers = {"content-type": "application/json", "content-length": str(len(json.dumps(payload)))}
        def raise_for_status(self): return None
        async def aiter_bytes(self): yield json.dumps(payload).encode()

    class RedirectResponse:
        status_code = 302
        headers = {"location": "http://127.0.0.1/video.mp4", "content-length": "0"}
        def raise_for_status(self): return None
        async def aiter_raw(self): yield b""

    called = []

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        called.append((url, kwargs))
        if "api.pexels.com" in url:
            yield APIResponse()
        else:
            yield RedirectResponse()

    monkeypatch.setattr(video_engine, "open_public_http_response", fake_open)
    target = tmp_path / "broll.mp4"
    with pytest.raises(ValueError, match="redirect blocked"):
        await video_engine._download_pexels("nature", target)
    assert not target.exists()
    assert len(called) == 2
    assert called[1][1]["timeout"] == 90.0


@pytest.mark.asyncio
async def test_pexels_rejects_asset_content_length_above_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(video_engine, "get_settings", lambda: SimpleNamespace(pexels_api_key="test-api-key"))
    monkeypatch.setattr(video_engine, "MAX_BROLL_DOWNLOAD_BYTES", 8)
    payload = {"videos": [{
        "id": 1, "url": "https://www.pexels.com/video/1/", "duration": 10,
        "video_files": [{
            "file_type": "video/mp4", "link": "https://videos.example/video.mp4",
            "width": 1080, "height": 1920, "size": 0,
        }],
    }]}

    class APIResponse:
        status_code = 200
        headers = {"content-type": "application/json", "content-length": str(len(json.dumps(payload)))}
        def raise_for_status(self): return None
        async def aiter_bytes(self): yield json.dumps(payload).encode()

    class MediaResponse:
        status_code = 200
        headers = {"content-type": "video/mp4", "content-length": "9"}
        def raise_for_status(self): return None
        async def aiter_raw(self): yield b"x" * 9

    @asynccontextmanager
    async def fake_open(url, **kwargs):
        if "api.pexels.com" in url:
            yield APIResponse()
        else:
            yield MediaResponse()

    monkeypatch.setattr(video_engine, "open_public_http_response", fake_open)
    target = tmp_path / "broll.mp4"
    with pytest.raises(ValueError, match="byte limit"):
        await video_engine._download_pexels("nature", target)
    assert not target.exists()


def test_video_duration_cap_rejects_nonfinite_or_long_duration():
    assert video_engine._bounded_duration(12.5, label="duration") == pytest.approx(12.5)
    for duration in (0, -1, float("inf"), float("nan"), 181):
        with pytest.raises(ValueError):
            video_engine._bounded_duration(duration, label="duration", max_seconds=180)


def test_competitor_fetch_route_requires_authentication(monkeypatch):
    async def deny_auth():
        raise HTTPException(401, "Authentication required")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, deny_auth)
    with TestClient(main.app) as client:
        response = client.post("/api/research/competitors", json={"urls": ["https://public.example"]})
    assert response.status_code == 401


def test_competitor_fetch_route_requires_workspace(monkeypatch):
    async def no_workspace():
        return {"email": "test@example.invalid", "user_id": "test-user", "workspace_id": None}

    called = []

    async def rate_limit(*args, **kwargs):
        called.append("rate-limit")

    async def spy(*args, **kwargs):
        called.append("fetch")

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, no_workspace)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", rate_limit)
    monkeypatch.setattr(main, "competitor_spy", spy)
    with TestClient(main.app) as client:
        response = client.post("/api/research/competitors", json={"urls": ["https://public.example"]})
    assert response.status_code == 403
    assert called == []


def test_competitor_fetch_route_applies_workspace_rate_limit(monkeypatch):
    workspace_id = "outbound-fetch-workspace"
    rate_calls = []
    fetch_calls = []

    async def authorized_user():
        return {
            "email": "researcher@example.invalid",
            "user_id": "researcher-user",
            "workspace_id": workspace_id,
            "workspace_role": "owner",
            "is_admin": False,
        }

    async def rate_limit(request, selected_workspace_id, *, video=False):
        rate_calls.append((selected_workspace_id, video))

    async def spy(urls):
        assert get_workspace_id() == workspace_id
        fetch_calls.append(urls)
        return [{"url": urls[0], "title": "Public sample"}]

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, authorized_user)
    monkeypatch.setattr(main, "workspace_generation_rate_limit", rate_limit)
    monkeypatch.setattr(main, "competitor_spy", spy)
    with TestClient(main.app) as client:
        response = client.post("/api/research/competitors", json={"urls": ["https://public.example"]})

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Public sample"
    assert rate_calls == [(workspace_id, False)]
    assert fetch_calls == [["https://public.example"]]


def test_competitor_fetch_route_rejects_oversized_url_strings(monkeypatch):
    async def authorized_user():
        return {"email": "researcher@example.invalid", "user_id": "researcher-user", "workspace_id": "workspace"}

    monkeypatch.setitem(main.app.dependency_overrides, main.require_auth, authorized_user)
    long_url = "https://public.example/" + ("a" * 2050)
    with TestClient(main.app) as client:
        response = client.post("/api/research/competitors", json={"urls": [long_url]})
    assert response.status_code == 422
