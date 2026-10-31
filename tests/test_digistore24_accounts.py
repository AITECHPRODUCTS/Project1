from __future__ import annotations

import httpx
import pytest
from types import SimpleNamespace

from backend.services import digistore24_accounts as ds24

API_KEY = "ds24-read-" + "k" * 40


def _marketplace():
    return {
        "result": "success",
        "entries": [
            {
                "id": 12345,
                "headline": "Practical AI Marketing Course",
                "description": "<b>Ethical</b> performance marketing training.",
                "productCategory": "Education",
                "price": 79.0,
                "currency": "EUR",
                "affiliateShare": 50,
                "statsAffiliateProfitVisitor": 2.75,
                "statsAffiliateProfitSale": 39.5,
                "statsStars": 4.7,
                "statsCountOrdersWAff": 321,
                "statsCancelRate": 3.2,
                "statsConversionRate": 2.8,
                "approvalStatus": "active",
                "salespageUrl": "https://vendor.example.test/course",
                "affiliateSupportPage": "https://vendor.example.test/affiliates",
            },
            {"id": None, "headline": "invalid"},
            {"id": 67890, "headline": "Other Product", "description": "Unrelated"},
        ],
    }


@pytest.fixture
def valid_settings(monkeypatch):
    monkeypatch.setattr(ds24, "get_settings", lambda: SimpleNamespace(
        app_session_secret="test-session-secret-that-is-long-enough-for-digistore24-tests"
    ))


@pytest.mark.asyncio
async def test_verify_uses_official_post_format_json_and_read_key_header(monkeypatch):
    calls = []

    async def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/ping/format/json"):
            return {"result": "success", "accountId": 123456}
        return _marketplace()

    monkeypatch.setattr(ds24, "request_public_json", fake_request)
    result = await ds24.verify_digistore24_api_key(API_KEY)
    assert [url for url, _ in calls] == [
        "https://www.digistore24.com/api/call/ping/format/json",
        "https://www.digistore24.com/api/call/listMarketplaceEntries/format/json",
    ]
    assert all(kwargs["method"] == "POST" for _, kwargs in calls)
    assert all(kwargs["headers"]["X-DS-API-KEY"] == API_KEY for _, kwargs in calls)
    assert all(kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded" for _, kwargs in calls)
    assert all(kwargs["data_body"] == {} for _, kwargs in calls)
    assert result == {
        "account_references": ["123456"],
        "marketplace_entry_count": 3,
        "capabilities": ["account.ping", "marketplace.entries.read"],
    }


@pytest.mark.asyncio
async def test_search_normalizes_provider_reported_metrics_without_guessing_units(monkeypatch):
    async def fake_request(url, **kwargs):
        return _marketplace()

    monkeypatch.setattr(ds24, "request_public_json", fake_request)
    report = await ds24.search_digistore24_marketplace(API_KEY, query="ethical performance", limit=10)
    assert report["result_count"] == 1
    entry = report["entries"][0]
    assert entry["external_id"] == "12345"
    assert entry["title"] == "Practical AI Marketing Course"
    assert entry["description"] == "Ethical performance marketing training."
    assert entry["price_amount"] == "79.0"
    assert entry["currency"] == "EUR"
    assert entry["affiliate_share"] == "50"
    assert entry["affiliate_profit_per_visitor"] == "2.75"
    assert entry["affiliate_profit_per_sale"] == "39.5"
    assert entry["stats_orders_with_affiliates"] == 321
    assert entry["approval_status"] == "active"
    assert entry["product_url"] == "https://vendor.example.test/course"
    assert "does not mean a vendor has approved" in report["note"]


@pytest.mark.asyncio
async def test_failed_business_result_and_http_auth_errors_are_classified(monkeypatch):
    async def failed(url, **kwargs):
        return {"result": "error", "code": "permission_denied", "message": "Missing read permission"}

    monkeypatch.setattr(ds24, "request_public_json", failed)
    with pytest.raises(ds24.Digistore24AccessError):
        await ds24.verify_digistore24_api_key(API_KEY)

    async def denied(url, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(ds24, "request_public_json", denied)
    with pytest.raises(ds24.Digistore24AccessError):
        await ds24.verify_digistore24_api_key(API_KEY)


@pytest.mark.asyncio
async def test_rate_limit_is_provider_unavailable(monkeypatch):
    async def limited(url, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(ds24, "request_public_json", limited)
    with pytest.raises(ds24.Digistore24ProviderUnavailable):
        await ds24.verify_digistore24_api_key(API_KEY)


def test_credential_encryption_version_and_fingerprint(valid_settings):
    ciphertext = ds24.encrypt_digistore24_api_key(API_KEY)
    assert ciphertext != API_KEY and API_KEY not in ciphertext
    assert ds24.decrypt_digistore24_api_key(ciphertext) == API_KEY
    assert ds24.fingerprint_digistore24_api_key(API_KEY) != API_KEY
    with pytest.raises(ds24.StoredDigistore24CredentialError):
        ds24.decrypt_digistore24_api_key(ciphertext, key_version=99)


@pytest.mark.asyncio
async def test_marketplace_search_input_bounds():
    with pytest.raises(ValueError, match="2–120"):
        await ds24.search_digistore24_marketplace(API_KEY, query="x")
    with pytest.raises(ValueError, match="between 1 and 50"):
        await ds24.search_digistore24_marketplace(API_KEY, query="course", limit=51)
