from __future__ import annotations

import base64
import hashlib
import hmac
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings
from backend.services.url_safety import request_public_json

API_BASE = "https://www.digistore24.com/api/call/"
PING = "ping"
MARKETPLACE = "listMarketplaceEntries"
KEY_VERSION = 1
MAX_ROWS = 1000


class Digistore24AccessError(RuntimeError):
    pass


class Digistore24ProviderUnavailable(RuntimeError):
    pass


class StoredDigistore24CredentialError(RuntimeError):
    pass


def _key() -> bytes:
    secret = str(get_settings().app_session_secret or "")
    if len(secret) < 32:
        raise StoredDigistore24CredentialError("APP_SESSION_SECRET is not configured strongly enough for provider credentials.")
    return hashlib.sha256(b"omni-affiliate-digistore24-credentials:v1:" + secret.encode()).digest()


def encrypt_digistore24_api_key(api_key: str) -> str:
    return Fernet(base64.urlsafe_b64encode(_key())).encrypt(api_key.encode()).decode("ascii")


def decrypt_digistore24_api_key(ciphertext: str, key_version: int = KEY_VERSION) -> str:
    if key_version != KEY_VERSION:
        raise StoredDigistore24CredentialError("Stored Digistore24 credential uses an unsupported encryption version.")
    try:
        return Fernet(base64.urlsafe_b64encode(_key())).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise StoredDigistore24CredentialError("Stored Digistore24 credential cannot be decrypted; reconnect the account.") from None


def fingerprint_digistore24_api_key(api_key: str) -> str:
    return hmac.new(_key(), api_key.encode(), hashlib.sha256).hexdigest()


def is_digistore24_api_key_format_valid(api_key: str) -> bool:
    value = str(api_key or "").strip()
    return 20 <= len(value) <= 512 and all(33 <= ord(char) <= 126 for char in value)


def _text(value: Any, limit: int = 4000) -> str:
    if value is None or isinstance(value, (dict, list, bool)):
        return ""
    value = re.sub(r"<[^>]{0,1000}>", " ", str(value))
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _decimal(value: Any, maximum: Decimal = Decimal("999999999999999")) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or abs(amount) > maximum:
        return None
    return format(amount, "f")


def _safe_https(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    return value.strip()


def _access_error(payload: dict[str, Any]) -> bool:
    code = _text(payload.get("code") or payload.get("error_code"), 80).casefold()
    message = _text(payload.get("message") or payload.get("error"), 300).casefold()
    combined = code + " " + message
    return any(part in combined for part in ("permission", "unauthorized", "not authorized", "api key", "access denied", "forbidden"))


async def _call(api_key: str, function: str) -> dict[str, Any]:
    if function not in {PING, MARKETPLACE}:
        raise ValueError("Unsupported Digistore24 API operation.")
    url = API_BASE + function + "/format/json"
    try:
        payload = await request_public_json(
            url,
            method="POST",
            headers={
                "X-DS-API-KEY": api_key,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "OmniAffiliateOS/1.0",
            },
            data_body={},
            timeout=12.0,
            max_bytes=2_000_000,
        )
    except httpx.HTTPStatusError as exc:
        status = int(exc.response.status_code)
        if status in {401, 403}:
            raise Digistore24AccessError("Digistore24 rejected the API key or its read permission. Check that the key is active and grants Read access.") from None
        if status == 429:
            raise Digistore24ProviderUnavailable("Digistore24 rate-limited the request. Retry after the provider cooldown.") from None
        raise Digistore24ProviderUnavailable(f"Digistore24 returned HTTP {status} for the requested read operation.") from None
    except (httpx.RequestError, TimeoutError):
        raise Digistore24ProviderUnavailable("Could not reach the Digistore24 API. Check provider availability and retry.") from None
    except ValueError:
        raise Digistore24ProviderUnavailable("Digistore24 returned an unsupported, redirected or invalid JSON response.") from None
    if not isinstance(payload, dict):
        raise Digistore24ProviderUnavailable("Digistore24 returned an unsupported API response.")
    if str(payload.get("result") or "").strip().casefold() != "success":
        if _access_error(payload):
            raise Digistore24AccessError("Digistore24 rejected the API key or its read permission.")
        raise Digistore24ProviderUnavailable("Digistore24 did not report a successful result.")
    return payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("entries")
    if rows is None and isinstance(payload.get("data"), dict):
        rows = payload["data"].get("entries")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise Digistore24ProviderUnavailable("Digistore24 marketplace response did not contain a bounded entries list.")
    return [row for row in rows if isinstance(row, dict)]


def _account_reference(payload: dict[str, Any]) -> list[str]:
    for field in ("accountId", "account_id", "affiliateId", "affiliate_id"):
        value = payload.get(field)
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            value = str(value).strip()
            if re.fullmatch(r"[0-9]{1,24}", value):
                return [value]
    return []


def _normalize_entry(item: dict[str, Any]) -> dict[str, Any] | None:
    identifier = item.get("id", item.get("entryId", item.get("entry_id")))
    if identifier is None or isinstance(identifier, bool):
        return None
    external_id = str(identifier).strip()
    title = _text(item.get("headline") or item.get("title"), 500)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", external_id) or not title:
        return None
    category = _text(item.get("productCategory") or item.get("product_category") or item.get("category"), 200)
    currency = item.get("currency")
    orders = item.get("statsCountOrdersWAff", item.get("stats_count_orders_w_aff"))
    if isinstance(orders, bool) or not isinstance(orders, (int, str)) or not re.fullmatch(r"[0-9]{1,12}", str(orders)):
        orders = None
    return {
        "external_id": external_id,
        "title": title,
        "description": _text(item.get("description"), 4000),
        "category": category or None,
        "product_url": _safe_https(item.get("salespageUrl") or item.get("salesPageUrl") or item.get("salespage_url")),
        "price_amount": _decimal(item.get("price")),
        "currency": str(currency).strip().upper() if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency.strip()) else None,
        "affiliate_share": _decimal(item.get("affiliateShare", item.get("affiliate_share"))),
        "affiliate_profit_per_visitor": _decimal(item.get("statsAffiliateProfitVisitor", item.get("stats_affiliate_profit_visitor"))),
        "affiliate_profit_per_sale": _decimal(item.get("statsAffiliateProfitSale", item.get("stats_affiliate_profit_sale"))),
        "stats_stars": _decimal(item.get("statsStars", item.get("stats_stars")), Decimal("1000000")),
        "stats_cancel_rate": _decimal(item.get("statsCancelRate", item.get("stats_cancel_rate")), Decimal("1000000")),
        "stats_conversion_rate": _decimal(item.get("statsConversionRate", item.get("stats_conversion_rate")), Decimal("1000000")),
        "stats_orders_with_affiliates": int(orders) if orders is not None else None,
        "approval_status": _text(item.get("approvalStatus") or item.get("approval_status"), 80) or None,
        "approval_status_message": _text(item.get("approvalStatusMsg") or item.get("approval_status_msg"), 500) or None,
        "vendor_name": _text(item.get("vendorName") or item.get("vendor_name"), 240) or None,
        "affiliate_support_url": _safe_https(item.get("affiliateSupportPage") or item.get("affiliate_support_page")),
        "product_created_at": _text(item.get("productCreatedAt") or item.get("product_created_at"), 80) or None,
        "stats_updated_at": _text(item.get("statsUpdatedAt") or item.get("stats_updated_at"), 80) or None,
    }


async def verify_digistore24_api_key(api_key: str) -> dict[str, Any]:
    ping = await _call(api_key, PING)
    marketplace = await _call(api_key, MARKETPLACE)
    entries = _rows(marketplace)
    return {
        "account_references": _account_reference(ping),
        "marketplace_entry_count": len(entries),
        "capabilities": ["account.ping", "marketplace.entries.read"],
    }


async def search_digistore24_marketplace(api_key: str, *, query: str, limit: int = 50) -> dict[str, Any]:
    normalized_query = str(query or "").strip()
    if len(normalized_query) < 2 or len(normalized_query) > 120:
        raise ValueError("Digistore24 marketplace search query must contain 2–120 characters.")
    if isinstance(limit, bool) or not 1 <= int(limit) <= 50:
        raise ValueError("Digistore24 marketplace search limit must be between 1 and 50.")
    rows = _rows(await _call(api_key, MARKETPLACE))
    entries = [entry for item in rows if (entry := _normalize_entry(item)) is not None]
    needle = normalized_query.casefold()
    matches = [
        entry for entry in entries
        if needle in " ".join(str(entry.get(field) or "") for field in ("title", "description", "category", "vendor_name")).casefold()
    ]
    return {
        "provider_id": "digistore24",
        "evidence_type": "provider_reported_affiliate_marketplace",
        "source_endpoint": MARKETPLACE,
        "query": normalized_query,
        "provider_list_count": len(rows),
        "normalized_count": len(entries),
        "result_count": min(len(matches), int(limit)),
        "entries": matches[: int(limit)],
        "commission_terms_status": "provider_marketplace_fields_only",
        "note": (
            "Marketplace fields and affiliate statistics are provider-reported snapshots, not an earnings forecast. "
            "Affiliate-share units and account-specific eligibility must be checked in Digistore24. A listing does not "
            "mean a vendor has approved your partnership or issued a promotional link. This read-only connector does "
            "not request approval, generate promotional links, publish content, or change the account."
        ),
    }
