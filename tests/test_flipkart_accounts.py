from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from backend.services import flipkart_accounts as flipkart


TRACKING_ID = "creator123"
API_TOKEN = "private-token-" + "x" * 32


def _directory():
    return {
        "apiGroups": {
            "affiliate": {
                "apiListings": {
                    "api": {"availableVariants": ["search", "offers"]},
                    "api_v1": {"availableVariants": ["search"]},
                }
            }
        }
    }


def _product_payload():
    return {
        "productInfoList": [
            {
                "productBaseInfoV1": {
                    "productId": "MOBABC123",
                    "title": "Sample Android Phone",
                    "productDescription": "Provider supplied product description",
                    "productBrand": "ExampleBrand",
                    "categoryPath": [[{"title": "Mobiles"}, {"title": "Smartphones"}]],
                    "productUrl": "https://www.flipkart.com/sample-phone/p/itmobabc123",
                    "imageUrls": {"400x400": "https://rukminim1.flixcart.com/image/400/400/sample.jpeg"},
                    "flipkartSellingPrice": {"amount": 12999, "currency": "INR"},
                    "maximumRetailPrice": {"amount": 15999, "currency": "INR"},
                    "inStock": True,
                    "discountPercentage": 18,
                }
            },
            {"unexpected": "shape"},
        ]
    }


def _offers_payload():
    return {
        "allOffersList": [
            {
                "title": "Weekend electronics offer",
                "description": "Provider supplied offer description",
                "url": "https://www.flipkart.com/offers/sample",
                "category": "Electronics",
                "startTime": "2026-10-29T00:00:00Z",
                "endTime": "2026-11-02T23:59:59Z",
                "availability": "LIVE",
                "imageUrls": {"400x400": "https://rukminim1.flixcart.com/image/400/400/offer.jpeg"},
            },
            {
                "title": "Unsafe offer URL",
                "url": "https://127.0.0.1/private",
                "availability": {"unexpected": "shape"},
            },
        ]
    }


@pytest.fixture
def valid_settings(monkeypatch):
    monkeypatch.setattr(
        flipkart,
        "get_settings",
        lambda: SimpleNamespace(app_session_secret="test-session-secret-that-is-long-enough-for-flipkart-tests"),
    )


@pytest.mark.asyncio
async def test_verification_calls_tracking_id_directory_and_auth_headers(monkeypatch):
    calls = []

    async def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return _directory()

    monkeypatch.setattr(flipkart, "request_public_json", fake_request)
    result = await flipkart.verify_flipkart_credentials(TRACKING_ID, API_TOKEN)
    url, kwargs = calls[0]
    assert url == f"https://affiliate-api.flipkart.net/affiliate/api/{TRACKING_ID}.json"
    assert kwargs["method"] == "GET"
    assert kwargs["headers"] == {
        "Fk-Affiliate-Id": TRACKING_ID,
        "Fk-Affiliate-Token": API_TOKEN,
        "Accept": "application/json",
        "User-Agent": "OmniAffiliateOS/1.0",
    }
    assert kwargs["timeout"] == 12.0 and kwargs["max_bytes"] == 256_000
    assert result["tracking_id"] == TRACKING_ID
    assert result["categories"] == ["api", "api_v1"]
    assert result["capabilities"] == ["product_feed.directory.read", "products.search", "offers.list"]


@pytest.mark.asyncio
async def test_directory_with_no_affiliate_product_categories_fails_closed(monkeypatch):
    async def fake_request(url, **kwargs):
        return {"apiGroups": {"affiliate": {"apiListings": {}}}}

    monkeypatch.setattr(flipkart, "request_public_json", fake_request)
    with pytest.raises(flipkart.FlipkartAccessError, match="no affiliate product-feed categories"):
        await flipkart.verify_flipkart_credentials(TRACKING_ID, API_TOKEN)


@pytest.mark.asyncio
async def test_product_keyword_search_uses_fixed_endpoint_and_limits_results(monkeypatch):
    calls = []

    async def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return _product_payload()

    monkeypatch.setattr(flipkart, "request_public_json", fake_request)
    report = await flipkart.search_flipkart_products(
        TRACKING_ID, API_TOKEN, query="android phone", result_count=10
    )
    url, kwargs = calls[0]
    assert url == "https://affiliate-api.flipkart.net/affiliate/1.0/search.json"
    assert kwargs["params"] == {"query": "android phone", "resultCount": 10}
    assert kwargs["headers"]["Fk-Affiliate-Id"] == TRACKING_ID
    assert kwargs["headers"]["Fk-Affiliate-Token"] == API_TOKEN
    assert report["evidence_type"] == "provider_reported_product_search"
    assert report["source_endpoint"] == "affiliate/1.0/search.json"
    assert report["result_count"] == 1
    product = report["products"][0]
    assert product["external_id"] == "MOBABC123"
    assert product["title"] == "Sample Android Phone"
    assert product["brand"] == "ExampleBrand"
    assert product["category"] == "Mobiles / Smartphones"
    assert product["price_amount"] == "12999"
    assert product["mrp_amount"] == "15999"
    assert product["currency"] == "INR"
    assert product["in_stock"] is True
    assert product["discount_percentage"] == "18"
    assert product["product_url"].startswith("https://www.flipkart.com/")
    assert product["image_url"].startswith("https://rukminim1.flixcart.com/")
    assert report["commission_terms_status"] == "not_exposed_by_product_search_endpoint"
    assert "cookie duration" in report["note"]
    assert "commission_rate" not in product


@pytest.mark.asyncio
async def test_product_search_rejects_invalid_query_and_more_than_ten_results():
    with pytest.raises(ValueError, match="2–200 characters"):
        await flipkart.search_flipkart_products(TRACKING_ID, API_TOKEN, query="x")
    with pytest.raises(ValueError, match="at most 10"):
        await flipkart.search_flipkart_products(TRACKING_ID, API_TOKEN, query="phone", result_count=11)


@pytest.mark.asyncio
async def test_product_search_rejects_bad_provider_money_and_filters_unsafe_urls(monkeypatch):
    payload = _product_payload()
    product = payload["productInfoList"][0]["productBaseInfoV1"]
    product["flipkartSellingPrice"] = {"amount": "NaN", "currency": "INR"}
    product["productUrl"] = "http://127.0.0.1/private"

    async def fake_request(url, **kwargs):
        return payload

    monkeypatch.setattr(flipkart, "request_public_json", fake_request)
    report = await flipkart.search_flipkart_products(TRACKING_ID, API_TOKEN, query="phone")
    normalized = report["products"][0]
    assert normalized["price_amount"] is None
    assert normalized["product_url"] is None


@pytest.mark.asyncio
async def test_active_offers_use_official_endpoint_and_drop_unsafe_records(monkeypatch):
    calls = []

    async def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return _offers_payload()

    monkeypatch.setattr(flipkart, "request_public_json", fake_request)
    report = await flipkart.fetch_flipkart_offers(TRACKING_ID, API_TOKEN, kind="all")
    url, kwargs = calls[0]
    assert url == "https://affiliate-api.flipkart.net/affiliate/offers/v1/all/json"
    assert kwargs["headers"]["Fk-Affiliate-Token"] == API_TOKEN
    assert report["result_count"] == 1
    offer = report["offers"][0]
    assert offer["title"] == "Weekend electronics offer"
    assert offer["availability_status"] == "LIVE"
    assert offer["is_available"] is True
    assert offer["start_at"] == "2026-10-29T00:00:00+00:00"
    assert offer["end_at"] == "2026-11-02T23:59:59+00:00"
    assert offer["offer_url"].startswith("https://www.flipkart.com/")
    assert report["commission_terms_status"] == "not_exposed_by_offer_feed"


@pytest.mark.asyncio
async def test_dotd_uses_documented_endpoint_and_unhashable_availability_does_not_crash(monkeypatch):
    calls = []

    async def fake_request(url, **kwargs):
        calls.append(url)
        return {
            "dotdList": [{
                "title": "Deal of the day",
                "url": "https://www.flipkart.com/deal",
                "availability": {"unexpected": "object"},
            }]
        }

    monkeypatch.setattr(flipkart, "request_public_json", fake_request)
    report = await flipkart.fetch_flipkart_offers(TRACKING_ID, API_TOKEN, kind="dotd")
    assert calls == ["https://affiliate-api.flipkart.net/affiliate/offers/v1/dotd/json"]
    assert report["offers"][0]["availability_status"] is None
    assert report["offers"][0]["is_available"] is None


@pytest.mark.asyncio
async def test_provider_auth_and_rate_limit_errors_are_classified(monkeypatch):
    async def forbidden(url, **kwargs):
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(flipkart, "request_public_json", forbidden)
    with pytest.raises(flipkart.FlipkartAccessError):
        await flipkart.verify_flipkart_credentials(TRACKING_ID, API_TOKEN)

    async def limited(url, **kwargs):
        request = httpx.Request("GET", url)
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(flipkart, "request_public_json", limited)
    with pytest.raises(flipkart.FlipkartProviderUnavailable, match="rate-limited"):
        await flipkart.fetch_flipkart_offers(TRACKING_ID, API_TOKEN)


def test_credentials_are_encrypted_versioned_and_fingerprinted_per_account(valid_settings):
    token = API_TOKEN
    ciphertext = flipkart.encrypt_flipkart_api_token(token)
    assert ciphertext != token and token not in ciphertext
    assert flipkart.decrypt_flipkart_api_token(ciphertext) == token
    fingerprint = flipkart.fingerprint_flipkart_credentials(TRACKING_ID, token)
    assert len(fingerprint) == 64 and token not in fingerprint
    assert fingerprint != flipkart.fingerprint_flipkart_credentials("other-id", token)
    with pytest.raises(flipkart.StoredFlipkartCredentialError, match="unsupported encryption version"):
        flipkart.decrypt_flipkart_api_token(ciphertext, key_version=99)
