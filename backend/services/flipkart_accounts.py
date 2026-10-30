from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings
from backend.services.url_safety import request_public_json

FLIPKART_DIRECTORY_URL = "https://affiliate-api.flipkart.net/affiliate/api/{tracking_id}.json"
FLIPKART_PRODUCT_SEARCH_URL = "https://affiliate-api.flipkart.net/affiliate/1.0/search.json"
FLIPKART_ACTIVE_OFFERS_URL = "https://affiliate-api.flipkart.net/affiliate/offers/v1/all/json"
FLIPKART_DOTD_OFFERS_URL = "https://affiliate-api.flipkart.net/affiliate/offers/v1/dotd/json"
CREDENTIAL_KEY_VERSION = 1
_TRACKING_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,99}$")


class FlipkartAccessError(RuntimeError):
    """Flipkart rejected the supplied affiliate credentials or permission."""


class FlipkartProviderUnavailable(RuntimeError):
    """Flipkart or its API response is unavailable or not usable."""


class StoredFlipkartCredentialError(RuntimeError):
    """The locally stored Flipkart token cannot be decrypted safely."""


def normalize_tracking_id(value: str) -> str:
    tracking_id = str(value or "").strip()
    if not _TRACKING_ID_RE.fullmatch(tracking_id):
        raise ValueError("Enter the Flipkart affiliate tracking ID shown in API settings.")
    return tracking_id


def _credential_key() -> bytes:
    secret = str(get_settings().app_session_secret or "")
    if len(secret) < 32:
        raise StoredFlipkartCredentialError(
            "APP_SESSION_SECRET is not configured strongly enough for provider credentials."
        )
    return hashlib.sha256(
        b"omni-affiliate-flipkart-credentials:v1:" + secret.encode("utf-8")
    ).digest()


def _cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_credential_key()))


def encrypt_flipkart_api_token(api_token: str) -> str:
    return _cipher().encrypt(api_token.encode("utf-8")).decode("ascii")


def decrypt_flipkart_api_token(ciphertext: str, key_version: int = CREDENTIAL_KEY_VERSION) -> str:
    if key_version != CREDENTIAL_KEY_VERSION:
        raise StoredFlipkartCredentialError(
            "Stored Flipkart credential uses an unsupported encryption version."
        )
    try:
        return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise StoredFlipkartCredentialError(
            "Stored Flipkart credential cannot be decrypted; reconnect the account."
        ) from None


def fingerprint_flipkart_credentials(tracking_id: str, api_token: str) -> str:
    normalized_id = normalize_tracking_id(tracking_id)
    material = (normalized_id + "\x00" + api_token).encode("utf-8")
    return hmac.new(_credential_key(), material, hashlib.sha256).hexdigest()


def _headers(tracking_id: str, api_token: str) -> dict[str, str]:
    return {
        "Fk-Affiliate-Id": normalize_tracking_id(tracking_id),
        "Fk-Affiliate-Token": api_token,
        "Accept": "application/json",
        "User-Agent": "OmniAffiliateOS/1.0",
    }


async def _request_json(
    url: str,
    *,
    tracking_id: str,
    api_token: str,
    params: dict[str, Any] | None = None,
    max_bytes: int = 1_000_000,
) -> dict[str, Any] | list[Any]:
    try:
        return await request_public_json(
            url,
            method="GET",
            params=params,
            headers=_headers(tracking_id, api_token),
            timeout=12.0,
            max_bytes=max_bytes,
        )
    except httpx.HTTPStatusError as exc:
        status = int(exc.response.status_code)
        if status in {401, 403}:
            raise FlipkartAccessError(
                "Flipkart rejected the affiliate tracking ID/token. Check account registration and API-token status."
            ) from None
        if status == 429:
            raise FlipkartProviderUnavailable(
                "Flipkart rate-limited the request. Wait before retrying."
            ) from None
        raise FlipkartProviderUnavailable(
            f"Flipkart returned HTTP {status} for the requested affiliate API operation."
        ) from None
    except (httpx.RequestError, TimeoutError):
        raise FlipkartProviderUnavailable(
            "Could not reach the Flipkart Affiliate API. Retry after checking provider availability."
        ) from None
    except ValueError:
        raise FlipkartProviderUnavailable(
            "Flipkart returned an unsupported, redirected or invalid JSON response."
        ) from None


def _directory_categories(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    api_groups = payload.get("apiGroups")
    affiliate_group = api_groups.get("affiliate") if isinstance(api_groups, dict) else None
    listings = affiliate_group.get("apiListings") if isinstance(affiliate_group, dict) else None
    if not isinstance(listings, dict):
        listings = payload.get("apiListings")
    if not isinstance(listings, dict):
        return []
    categories = []
    for key, value in listings.items():
        if (
            isinstance(key, str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", key)
            and isinstance(value, dict)
        ):
            categories.append(key)
    return sorted(set(categories), key=str.casefold)


async def verify_flipkart_credentials(tracking_id: str, api_token: str) -> dict[str, Any]:
    """Verify credentials with the official Product Feed Listing endpoint."""
    normalized_id = normalize_tracking_id(tracking_id)
    payload = await _request_json(
        FLIPKART_DIRECTORY_URL.format(tracking_id=normalized_id),
        tracking_id=normalized_id,
        api_token=api_token,
        max_bytes=256_000,
    )
    categories = _directory_categories(payload)
    if not categories:
        raise FlipkartAccessError(
            "Flipkart authorized the request but returned no affiliate product-feed categories."
        )
    return {
        "tracking_id": normalized_id,
        "categories": categories,
        "capabilities": ["product_feed.directory.read", "products.search", "offers.list"],
    }


def _safe_provider_url(value: Any, *, allowed_suffixes: tuple[str, ...]) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username
        or parsed.password
        or not any(hostname == suffix or hostname.endswith("." + suffix) for suffix in allowed_suffixes)
    ):
        return None
    return value.strip()


def _money(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    amount = value.get("amount")
    currency = value.get("currency")
    if amount is None:
        return None, currency if isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency) else None
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return None, None
    if not decimal_amount.is_finite() or abs(decimal_amount) > Decimal("999999999999999"):
        return None, None
    normalized_currency = currency if isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency) else None
    return format(decimal_amount, "f"), normalized_currency


def _image_url(value: Any) -> str | None:
    urls: list[str] = []
    if isinstance(value, dict):
        priority = ("400x400", "200x200", "800x800", "unknown")
        urls.extend(value[key] for key in priority if isinstance(value.get(key), str))
        urls.extend(item for key, item in value.items() if key not in priority and isinstance(item, str))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                urls.append(item["url"])
    for candidate in urls:
        safe = _safe_provider_url(candidate, allowed_suffixes=("flipkart.com", "flixcart.com"))
        if safe and safe.startswith("https://"):
            return safe
    return None


def _category(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip()[:200] or None
    if isinstance(value, list):
        names = []
        for part in value:
            if isinstance(part, dict):
                title = part.get("title") or part.get("node_name")
                if isinstance(title, str) and title.strip():
                    names.append(title.strip())
            elif isinstance(part, list):
                names.extend(
                    str(child.get("title") or child.get("node_name")).strip()
                    for child in part
                    if isinstance(child, dict) and (child.get("title") or child.get("node_name"))
                )
        return " / ".join(names[:8])[:200] or None
    return None


def _normalize_product(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    base = item.get("productBaseInfoV1")
    if not isinstance(base, dict):
        base = item.get("productBaseInfo")
    if not isinstance(base, dict):
        return None
    identifier = base.get("productId")
    title = base.get("title")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,120}", identifier):
        return None
    if not isinstance(title, str) or not title.strip():
        return None
    selling = base.get("flipkartSpecialPrice") or base.get("flipkartSellingPrice") or base.get("sellingPrice")
    mrp = base.get("maximumRetailPrice") or base.get("mrp")
    selling_amount, selling_currency = _money(selling)
    mrp_amount, mrp_currency = _money(mrp)
    raw_stock = base.get("inStock")
    in_stock = raw_stock if isinstance(raw_stock, bool) else None
    discount = base.get("discountPercentage")
    try:
        discount_value = Decimal(str(discount)) if discount is not None else None
    except (InvalidOperation, ValueError, TypeError):
        discount_value = None
    if discount_value is not None and (
        not discount_value.is_finite() or discount_value < 0 or discount_value > 100
    ):
        discount_value = None
    product_url = _safe_provider_url(
        base.get("productUrl"), allowed_suffixes=("flipkart.com", "fkrt.it")
    )
    attributes = base.get("attributes") if isinstance(base.get("attributes"), dict) else {}
    return {
        "external_id": identifier,
        "title": title.strip()[:500],
        "description": str(base.get("productDescription") or "")[:4000],
        "brand": str(base.get("productBrand") or "")[:200] or None,
        "category": _category(base.get("categoryPath") or base.get("categoryPaths")),
        "product_url": product_url,
        "image_url": _image_url(base.get("imageUrls")),
        "price_amount": selling_amount,
        "mrp_amount": mrp_amount,
        "currency": selling_currency or mrp_currency,
        "in_stock": in_stock,
        "discount_percentage": format(discount_value, "f") if discount_value is not None else None,
        "attributes": {
            str(key)[:100]: str(value)[:500]
            for key, value in list(attributes.items())[:40]
            if isinstance(key, str) and value is not None and not isinstance(value, (dict, list))
        },
    }


async def search_flipkart_products(
    tracking_id: str,
    api_token: str,
    *,
    query: str,
    result_count: int = 10,
) -> dict[str, Any]:
    normalized_id = normalize_tracking_id(tracking_id)
    normalized_query = str(query or "").strip()
    if len(normalized_query) < 2 or len(normalized_query) > 200:
        raise ValueError("Flipkart product search query must contain 2–200 characters.")
    if not 1 <= int(result_count) <= 10:
        raise ValueError("Flipkart keyword search supports at most 10 products per request.")
    payload = await _request_json(
        FLIPKART_PRODUCT_SEARCH_URL,
        tracking_id=normalized_id,
        api_token=api_token,
        params={"query": normalized_query, "resultCount": int(result_count)},
        max_bytes=1_500_000,
    )
    raw_rows = payload.get("productInfoList") if isinstance(payload, dict) else None
    if raw_rows is None and isinstance(payload, dict) and isinstance(payload.get("products"), dict):
        raw_rows = payload["products"].get("productInfoList")
    if not isinstance(raw_rows, list):
        raise FlipkartProviderUnavailable("Flipkart product search returned an unsupported product list.")
    products = []
    for item in raw_rows[: int(result_count)]:
        normalized = _normalize_product(item)
        if normalized is not None:
            products.append(normalized)
    return {
        "provider_id": "flipkart",
        "evidence_type": "provider_reported_product_search",
        "source_endpoint": "affiliate/1.0/search.json",
        "query": normalized_query,
        "requested_count": int(result_count),
        "result_count": len(products),
        "products": products,
        "commission_terms_status": "not_exposed_by_product_search_endpoint",
        "note": "Product attributes, current prices and stock are provider-reported at retrieval time. Commission rate, cookie duration, payout terms, account eligibility and approval were not supplied by this endpoint.",
    }


def _provider_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if abs(value) > 100_000_000_000:
            value = value / 1000
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _normalize_offer(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    offer_url = _safe_provider_url(item.get("url"), allowed_suffixes=("flipkart.com", "fkrt.it"))
    if not isinstance(title, str) or not title.strip() or not offer_url:
        return None
    start_at = _provider_datetime(item.get("startTime"))
    end_at = _provider_datetime(item.get("endTime"))
    availability = item.get("availability")
    availability_status = availability if availability in {"LIVE", "OOS"} else None
    image = _image_url(item.get("imageUrls"))
    external_id = hashlib.sha256(
        (title.strip() + "\x00" + offer_url).encode("utf-8")
    ).hexdigest()
    return {
        "external_id": external_id,
        "title": title.strip()[:500],
        "description": str(item.get("description") or "")[:4000],
        "category": str(item.get("category") or "")[:200] or None,
        "offer_url": offer_url,
        "image_url": image,
        "availability_status": availability_status,
        "is_available": True if availability_status == "LIVE" else False if availability_status == "OOS" else None,
        "start_at": start_at.isoformat() if start_at else None,
        "end_at": end_at.isoformat() if end_at else None,
    }


async def fetch_flipkart_offers(
    tracking_id: str,
    api_token: str,
    *,
    kind: str = "all",
) -> dict[str, Any]:
    normalized_id = normalize_tracking_id(tracking_id)
    if kind not in {"all", "dotd"}:
        raise ValueError("Offer kind must be 'all' or 'dotd'.")
    endpoint = FLIPKART_ACTIVE_OFFERS_URL if kind == "all" else FLIPKART_DOTD_OFFERS_URL
    payload = await _request_json(
        endpoint,
        tracking_id=normalized_id,
        api_token=api_token,
        max_bytes=2_000_000,
    )
    key = "allOffersList" if kind == "all" else "dotdList"
    raw_rows = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list):
        raise FlipkartProviderUnavailable("Flipkart offers API returned an unsupported offer list.")
    offers = []
    for item in raw_rows[:1000]:
        normalized = _normalize_offer(item)
        if normalized is not None:
            offers.append(normalized)
    return {
        "provider_id": "flipkart",
        "evidence_type": "provider_reported_active_offers",
        "source_endpoint": "affiliate/offers/v1/all/json" if kind == "all" else "affiliate/offers/v1/dotd/json",
        "offer_kind": kind,
        "result_count": len(offers),
        "offers": offers,
        "commission_terms_status": "not_exposed_by_offer_feed",
        "note": "Offer title, destination, dates and availability are provider-reported. Commission rate, cookie duration, payout terms, account eligibility and promotion approval were not supplied by this endpoint.",
    }
