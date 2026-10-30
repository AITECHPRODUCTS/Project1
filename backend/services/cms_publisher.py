from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from bs4 import BeautifulSoup

from backend.config import get_settings
from backend.core.errors import IntegrationNotConfiguredError
from backend.services.url_safety import (
    open_public_http_response,
    read_limited_response,
    validate_public_http_url,
)


CMS_RESPONSE_MAX_BYTES = 2_000_000
CMS_REQUEST_TIMEOUT_SECONDS = 25.0


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _ghost_jwt(key: str) -> str:
    try:
        kid, secret_hex = key.split(":", 1)
        secret = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise ValueError("Ghost API key must be id:hex-secret") from exc
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}, separators=(",", ":")).encode())
    signing = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{_b64(hmac.new(secret, signing, hashlib.sha256).digest())}"


def sanitize_article(markup: str, disclosure: str) -> str:
    soup = BeautifulSoup(markup, "html.parser")
    for node in soup.find_all(["iframe", "object", "embed", "form", "input", "button"]):
        node.decompose()
    for node in soup.find_all("script"):
        if node.get("type") != "application/ld+json":
            node.decompose()
    for node in soup.find_all(True):
        for key in list(node.attrs):
            if key.lower().startswith("on") or key.lower() == "srcdoc":
                del node.attrs[key]
        for key in ("src", "href"):
            value = node.get(key)
            if isinstance(value, str) and value.strip().lower().startswith(("javascript:", "data:text/html")):
                del node.attrs[key]
    paragraph = soup.new_tag("p", attrs={"class": "affiliate-disclosure"})
    paragraph.string = disclosure[:1200] if disclosure else "Disclosure: This article may contain affiliate links; a commission may be earned."
    (soup.body or soup).append(paragraph)
    return str(soup)


async def _post_cms_json(
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    async with open_public_http_response(
        url,
        method="POST",
        json_body=payload,
        headers=headers,
        timeout=CMS_REQUEST_TIMEOUT_SECONDS,
    ) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("CMS provider redirects are not followed")
        response.raise_for_status()
        raw = await read_limited_response(response, max_bytes=CMS_RESPONSE_MAX_BYTES)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("CMS provider returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("CMS provider returned an unexpected response object")
    return result


async def publish_article(
    *,
    provider: str,
    title: str,
    article_html: str,
    canonical_url: str,
    status: str = "draft",
    tags: list[str] | None = None,
    disclosure: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    if provider not in {"wordpress", "ghost"}:
        raise ValueError("provider must be wordpress or ghost")
    if status not in {"draft", "publish"}:
        raise ValueError("status must be draft or publish")
    if status == "publish" and not settings.cms_publish_execute:
        raise IntegrationNotConfiguredError("CMS_PUBLISH_EXECUTE=true required for actual publishing")
    if not title.strip():
        raise ValueError("title required")

    await validate_public_http_url(canonical_url)
    content = sanitize_article(article_html, disclosure)

    if provider == "wordpress":
        base = os.getenv("WORDPRESS_SITE_URL", "").rstrip("/")
        username = os.getenv("WORDPRESS_USERNAME", "")
        password = os.getenv("WORDPRESS_APPLICATION_PASSWORD", "")
        if not all((base, username, password)):
            raise IntegrationNotConfiguredError("Configure WordPress site URL, username and application password")
        credential = base64.b64encode(f"{username}:{password}".encode()).decode()
        data = await _post_cms_json(
            base + "/wp-json/wp/v2/posts",
            payload={"title": title[:300], "content": content, "status": status},
            headers={"Authorization": f"Basic {credential}", "Accept": "application/json"},
        )
        return {
            "provider": provider,
            "status": data.get("status"),
            "remote_id": data.get("id"),
            "url": data.get("link"),
            "disclosure_injected": True,
        }

    base = os.getenv("GHOST_SITE_URL", "").rstrip("/")
    key = os.getenv("GHOST_ADMIN_API_KEY", "")
    if not base or not key:
        raise IntegrationNotConfiguredError("Configure GHOST_SITE_URL and GHOST_ADMIN_API_KEY")
    payload = {
        "posts": [{
            "title": title[:300],
            "html": content,
            "status": status,
            "tags": [{"name": tag[:100]} for tag in (tags or [])[:20]],
        }]
    }
    data = await _post_cms_json(
        base + "/ghost/api/admin/posts/?source=html",
        payload=payload,
        headers={"Authorization": f"Ghost {_ghost_jwt(key)}", "Accept-Version": "v5.0", "Accept": "application/json"},
    )
    posts = data.get("posts")
    if not isinstance(posts, list) or not posts or not isinstance(posts[0], dict):
        raise ValueError("Ghost returned an unexpected posts response")
    result = posts[0]
    return {
        "provider": provider,
        "status": result.get("status"),
        "remote_id": result.get("id"),
        "url": result.get("url"),
        "disclosure_injected": True,
    }
