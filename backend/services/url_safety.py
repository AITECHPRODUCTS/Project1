
from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

import httpx

DNS_TIMEOUT_SECONDS = 3.0


async def _resolve_public_target(url: str) -> tuple[httpx.URL, str, str]:
    try:
        target = httpx.URL(url)
    except Exception as exc:
        raise ValueError("Only absolute HTTP(S) URLs are allowed") from exc
    if target.scheme not in {"http", "https"} or not target.host:
        raise ValueError("Only absolute HTTP(S) URLs are allowed")
    if target.username or target.password:
        raise ValueError("URLs containing credentials are not allowed")

    hostname = target.host.lower().rstrip(".")
    if (
        hostname in {"localhost", "localhost.localdomain"}
        or hostname.endswith((".localhost", ".local", ".internal", ".test", ".home", ".lan", ".corp"))
    ):
        raise ValueError("Local/private hostname blocked")
    port = target.port or (443 if target.scheme == "https" else 80)

    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            async with asyncio.timeout(DNS_TIMEOUT_SECONDS):
                answers = await asyncio.to_thread(
                    socket.getaddrinfo,
                    hostname,
                    port,
                    0,
                    socket.SOCK_STREAM,
                )
        except TimeoutError as exc:
            raise ValueError("Public hostname DNS lookup timed out") from exc
        except OSError as exc:
            raise ValueError("Public hostname DNS lookup failed") from exc
        addresses = []
        for answer in answers:
            try:
                addresses.append(ipaddress.ip_address(answer[4][0].split("%", 1)[0]))
            except (ValueError, IndexError, TypeError) as exc:
                raise ValueError("Hostname returned an invalid IP address") from exc

    if not addresses:
        raise ValueError("Hostname has no addresses")
    if any(not address.is_global for address in addresses):
        raise ValueError(
            "Private, loopback, link-local, multicast or reserved destinations are blocked"
        )
    return target, hostname, str(addresses[0])


async def validate_public_http_url(url: str) -> str:
    """Admission-time validation; actual fetches must use the pinned helper too."""
    await _resolve_public_target(url)
    return url


@asynccontextmanager
async def open_public_http_response(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    data_body: dict[str, Any] | None = None,
    timeout: float = 12.0,
) -> AsyncIterator[httpx.Response]:
    """Open a request pinned to a vetted public IP, preserving Host and TLS SNI.

    GET/HEAD are for public reads; POST is for fixed authenticated provider
    integrations. Redirects and ambient proxy configuration remain disabled.
    """
    method = method.upper()
    if method not in {"GET", "HEAD", "POST"}:
        raise ValueError("Public fetch helper only supports GET, HEAD and POST")
    if method != "POST" and (json_body is not None or data_body is not None):
        raise ValueError("Request bodies are only supported for POST")
    if json_body is not None and data_body is not None:
        raise ValueError("Choose JSON or form-encoded data, not both")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    target, hostname, connect_ip = await _resolve_public_target(url)
    default_port = 443 if target.scheme == "https" else 80
    host_header = f"[{hostname}]" if ":" in hostname else hostname
    if target.port and target.port != default_port:
        host_header = f"{host_header}:{target.port}"

    client_timeout = httpx.Timeout(timeout, connect=min(4.0, timeout))
    transport = httpx.AsyncHTTPTransport(retries=0)
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            transport=transport,
            timeout=client_timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            request = client.build_request(
                method, str(target), params=params, headers=headers, json=json_body, data=data_body
            )
            request.url = request.url.copy_with(host=connect_ip)
            request.headers["Host"] = host_header
            if target.scheme == "https":
                request.extensions["sni_hostname"] = hostname
            response = await client.send(request, stream=True)
            try:
                yield response
            finally:
                await response.aclose()


def declared_content_length(response: httpx.Response, max_bytes: int) -> int | None:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    raw = response.headers.get("content-length")
    if raw is None:
        return None
    try:
        length = int(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid response Content-Length") from exc
    if length < 0:
        raise ValueError("Invalid response Content-Length")
    if length > max_bytes:
        raise ValueError("Response exceeds byte limit")
    return length


async def read_limited_response(
    response: httpx.Response, *, max_bytes: int, raw: bool = False
) -> bytes:
    declared_content_length(response, max_bytes)
    chunks: list[bytes] = []
    size = 0
    stream = response.aiter_raw() if raw else response.aiter_bytes()
    async for chunk in stream:
        size += len(chunk)
        if size > max_bytes:
            raise ValueError("Response exceeds byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


async def request_public_json(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    data_body: dict[str, Any] | None = None,
    timeout: float = 12.0,
    max_bytes: int = 2_000_000,
) -> dict[str, Any] | list[Any]:
    """Request JSON from a fixed/configured public provider via the pinned transport."""
    async with open_public_http_response(
        url, method=method, params=params, headers=headers,
        json_body=json_body, data_body=data_body, timeout=timeout,
    ) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("Public provider redirects are not followed")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in {"application/json", "application/problem+json"}:
            raise ValueError(f"Unsupported provider response content type: {content_type}")
        body = await read_limited_response(response, max_bytes=max_bytes)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("Public provider returned invalid JSON") from exc
    if not isinstance(payload, (dict, list)):
        raise ValueError("Public provider returned an unexpected JSON response")
    return payload


async def fetch_public_page(
    url: str, *, max_bytes: int = 2_000_000, timeout: float = 12.0
) -> tuple[str, str, int]:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    headers = {
        "User-Agent": "AffiliateOSResearch/0.1",
        "Accept": "text/html,text/plain,application/xhtml+xml",
    }
    async with open_public_http_response(url, headers=headers, timeout=timeout) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("Redirect not followed; validate the redirected URL separately")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
            raise ValueError(f"Unsupported content type: {content_type}")
        body = await read_limited_response(response, max_bytes=max_bytes)
        return body.decode("utf-8", errors="replace"), content_type, response.status_code
