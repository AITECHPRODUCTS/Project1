from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from backend.services import cms_publisher


def _response(payload: bytes, *, status: int = 201, headers: dict[str, str] | None = None):
    response_headers = headers or {
        "content-type": "application/json",
        "content-length": str(len(payload)),
    }

    class Response:
        def __init__(self):
            self.status_code = status
            self.headers = response_headers

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        async def aiter_bytes(self):
            yield payload

    return Response()


@pytest.mark.asyncio
async def test_wordpress_post_uses_pinned_transport_with_auth_and_bounded_response(monkeypatch):
    monkeypatch.setattr(cms_publisher, "get_settings", lambda: SimpleNamespace(cms_publish_execute=False))
    monkeypatch.setenv("WORDPRESS_SITE_URL", "https://cms.example")
    monkeypatch.setenv("WORDPRESS_USERNAME", "publisher")
    monkeypatch.setenv("WORDPRESS_APPLICATION_PASSWORD", "app-password")
    async def validate(url: str) -> str:
        return url
    monkeypatch.setattr(cms_publisher, "validate_public_http_url", validate)

    calls: list[dict[str, Any]] = []
    @asynccontextmanager
    async def fake_open(url, *, method, params=None, headers=None, json_body=None, timeout=12):
        calls.append({"url": url, "method": method, "headers": headers, "body": json_body, "timeout": timeout})
        yield _response(json.dumps({"id": 42, "status": "draft", "link": "https://cms.example/post"}).encode())

    monkeypatch.setattr(cms_publisher, "open_public_http_response", fake_open)
    result = await cms_publisher.publish_article(
        provider="wordpress",
        title="Reviewed draft",
        article_html="<p>A sufficiently useful and reviewed article body.</p>",
        canonical_url="https://site.example/canonical",
        status="draft",
        disclosure="Affiliate disclosure.",
    )

    assert result["remote_id"] == 42
    assert calls[0]["url"] == "https://cms.example/wp-json/wp/v2/posts"
    assert calls[0]["method"] == "POST"
    assert calls[0]["timeout"] == 25.0
    assert calls[0]["headers"]["Authorization"].startswith("Basic ")
    assert calls[0]["body"]["status"] == "draft"
    assert "Affiliate disclosure." in calls[0]["body"]["content"]


@pytest.mark.asyncio
async def test_ghost_post_uses_pinned_transport_and_response_shape(monkeypatch):
    monkeypatch.setattr(cms_publisher, "get_settings", lambda: SimpleNamespace(cms_publish_execute=False))
    monkeypatch.setenv("GHOST_SITE_URL", "https://ghost.example")
    monkeypatch.setenv("GHOST_ADMIN_API_KEY", "test-kid:aa")
    async def validate(url: str) -> str:
        return url
    monkeypatch.setattr(cms_publisher, "validate_public_http_url", validate)

    calls = []
    @asynccontextmanager
    async def fake_open(url, *, method, params=None, headers=None, json_body=None, timeout=12):
        calls.append({"url": url, "method": method, "headers": headers, "body": json_body, "timeout": timeout})
        yield _response(json.dumps({"posts": [{"id": "ghost-1", "status": "draft", "url": "https://ghost.example/post"}]}).encode())

    monkeypatch.setattr(cms_publisher, "open_public_http_response", fake_open)
    result = await cms_publisher.publish_article(
        provider="ghost",
        title="Reviewed draft",
        article_html="<p>A sufficiently useful and reviewed article body.</p>",
        canonical_url="https://site.example/canonical",
        status="draft",
    )

    assert result["remote_id"] == "ghost-1"
    assert calls[0]["url"] == "https://ghost.example/ghost/api/admin/posts/?source=html"
    assert calls[0]["method"] == "POST"
    assert calls[0]["headers"]["Authorization"].startswith("Ghost ")
    assert calls[0]["body"]["posts"][0]["status"] == "draft"


@pytest.mark.asyncio
async def test_cms_redirect_is_rejected_without_following_provider_location(monkeypatch):
    monkeypatch.setattr(cms_publisher, "get_settings", lambda: SimpleNamespace(cms_publish_execute=False))
    monkeypatch.setenv("WORDPRESS_SITE_URL", "https://cms.example")
    monkeypatch.setenv("WORDPRESS_USERNAME", "publisher")
    monkeypatch.setenv("WORDPRESS_APPLICATION_PASSWORD", "app-password")
    async def validate(url: str) -> str:
        return url
    monkeypatch.setattr(cms_publisher, "validate_public_http_url", validate)

    called = []
    @asynccontextmanager
    async def fake_open(url, *, method, params=None, headers=None, json_body=None, timeout=12):
        called.append(url)
        yield _response(b"", status=302, headers={"location": "http://127.0.0.1/admin", "content-length": "0"})

    monkeypatch.setattr(cms_publisher, "open_public_http_response", fake_open)
    with pytest.raises(ValueError, match="redirects are not followed"):
        await cms_publisher.publish_article(
            provider="wordpress",
            title="Reviewed draft",
            article_html="<p>A sufficiently useful and reviewed article body.</p>",
            canonical_url="https://site.example/canonical",
            status="draft",
        )
    assert called == ["https://cms.example/wp-json/wp/v2/posts"]


@pytest.mark.asyncio
async def test_cms_response_byte_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(cms_publisher, "get_settings", lambda: SimpleNamespace(cms_publish_execute=False))
    monkeypatch.setenv("WORDPRESS_SITE_URL", "https://cms.example")
    monkeypatch.setenv("WORDPRESS_USERNAME", "publisher")
    monkeypatch.setenv("WORDPRESS_APPLICATION_PASSWORD", "app-password")
    async def validate(url: str) -> str:
        return url
    monkeypatch.setattr(cms_publisher, "validate_public_http_url", validate)

    @asynccontextmanager
    async def fake_open(url, *, method, params=None, headers=None, json_body=None, timeout=12):
        yield _response(b"{}", status=201, headers={"content-type": "application/json", "content-length": str(cms_publisher.CMS_RESPONSE_MAX_BYTES + 1)})

    monkeypatch.setattr(cms_publisher, "open_public_http_response", fake_open)
    with pytest.raises(ValueError, match="byte limit"):
        await cms_publisher.publish_article(
            provider="wordpress",
            title="Reviewed draft",
            article_html="<p>A sufficiently useful and reviewed article body.</p>",
            canonical_url="https://site.example/canonical",
            status="draft",
        )
