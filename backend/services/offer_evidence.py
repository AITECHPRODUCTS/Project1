from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from ipaddress import ip_address
from urllib.parse import parse_qsl, urlparse
from typing import Any

from bs4 import BeautifulSoup

from backend.services.url_safety import fetch_public_page

MAX_SOURCE_URLS = 10
MAX_SOURCE_BYTES = 1_000_000
MAX_EXCERPT_CHARS = 4_000
SENSITIVE_QUERY_PARAMETER = re.compile(
    r"(?:access[_-]?token|api[_-]?key|auth(?:orization)?|client[_-]?secret|"
    r"credential|password|secret|signature|session|token|code)",
    re.IGNORECASE,
)


def _validate_source_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if (
        len(url) > 2048
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or (parsed.port is not None and parsed.port != 443)
    ):
        raise ValueError("Evidence sources must be standard-port absolute HTTPS URLs without credentials")
    try:
        address = ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Evidence sources must not use private or non-public IP addresses")
    if any(SENSITIVE_QUERY_PARAMETER.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise ValueError("Evidence source URLs must not contain credential-like query parameters")
    return url


async def capture_offer_source_snapshots(source_urls: list[str]) -> list[dict[str, Any]]:
    """Capture bounded public-page evidence; a snapshot is not proof that a claim is true."""
    if not isinstance(source_urls, list) or not 1 <= len(source_urls) <= MAX_SOURCE_URLS:
        raise ValueError(f"Provide between one and {MAX_SOURCE_URLS} source URLs")

    urls: list[str] = []
    for raw in source_urls:
        if not isinstance(raw, str):
            raise ValueError("Each evidence source must be a URL string")
        url = _validate_source_url(raw)
        if url not in urls:
            urls.append(url)
    if not urls:
        raise ValueError("At least one unique evidence source is required")

    semaphore = asyncio.Semaphore(4)

    async def capture(index: int, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        base: dict[str, Any] = {
            "source_id": f"E{index:02d}",
            "source_url": url,
            "source_host": (parsed.hostname or "")[:253].lower(),
            "title": "",
            "description": "",
            "excerpt": "",
            "response_sha256": None,
            "excerpt_sha256": None,
            "http_status": None,
            "content_type": "",
            "fetch_status": "fetch_failed",
            "error_code": None,
            "fetched_at": datetime.now(timezone.utc),
        }
        try:
            async with semaphore:
                body, content_type, http_status = await fetch_public_page(
                    url, max_bytes=MAX_SOURCE_BYTES, timeout=12.0
                )
            media_type = str(content_type or "").split(";", 1)[0].strip().lower()
            if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                raise ValueError("Unsupported source content type")
            if not isinstance(http_status, int) or not 200 <= http_status < 300:
                raise ValueError("Source did not return a successful HTTP status")

            response_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            soup = BeautifulSoup(body, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
                "meta", attrs={"property": "og:description"}
            )
            description = str(meta.get("content") or "") if meta else ""
            for element in soup(["script", "style", "nav", "footer", "header", "noscript", "form", "svg"]):
                element.decompose()
            excerpt = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()[:MAX_EXCERPT_CHARS]
            excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest() if excerpt else None
            return {
                **base,
                "title": title[:500],
                "description": description[:1200],
                "excerpt": excerpt,
                "response_sha256": response_hash,
                "excerpt_sha256": excerpt_hash,
                "http_status": http_status,
                "content_type": str(content_type or "")[:120],
                "fetch_status": "fetched",
                "fetched_at": datetime.now(timezone.utc),
            }
        except Exception as exc:
            return {**base, "error_code": type(exc).__name__[:80]}

    return list(await asyncio.gather(*(capture(index, url) for index, url in enumerate(urls, start=1))))
