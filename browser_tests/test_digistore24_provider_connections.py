from __future__ import annotations

import json
import os
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")
API_KEY = "ds24-read-" + "b" * 40


def _fulfill(route, payload: dict, status: int = 200):
    route.fulfill(
        status=status,
        content_type="application/json",
        headers={
            "access-control-allow-origin": "http://127.0.0.1:3100",
            "access-control-allow-credentials": "true",
        },
        body=json.dumps(payload),
    )


def test_digistore24_connect_search_saved_marketplace_and_disconnect():
    connections = []
    seen = {"connect": None, "search": None, "disconnect": False}
    row = {
        "id": "ds-1",
        "provider_id": "digistore24",
        "status": "connected_read_only",
        "account_nicknames": ["123456"],
        "capabilities": ["account.ping", "marketplace.entries.read"],
        "permissions_verified": ["Marketplace entries read"],
        "credential_present": True,
        "last_checked_at": "2026-10-31T06:00:00+00:00",
        "last_error_code": None,
        "created_at": None,
    }
    report = {
        "provider_id": "digistore24",
        "evidence_type": "provider_reported_affiliate_marketplace",
        "source_endpoint": "listMarketplaceEntries",
        "query": "marketing",
        "result_count": 1,
        "persisted_count": 1,
        "source_checked_at": "2026-10-31T06:00:00+00:00",
        "commission_terms_status": "provider_marketplace_fields_only",
        "note": "Provider-reported marketplace metrics only. Listings do not equal accepted partnerships.",
        "entries": [{
            "external_id": "12345",
            "title": "Practical AI Marketing Course",
            "description": "Ethical affiliate marketing training.",
            "category": "Education",
            "product_url": "https://vendor.example.test/course",
            "price_amount": "79.0",
            "currency": "EUR",
            "affiliate_share": "50",
            "affiliate_profit_per_visitor": "2.75",
            "affiliate_profit_per_sale": "39.5",
            "stats_stars": "4.7",
            "stats_cancel_rate": "3.2",
            "stats_conversion_rate": "2.8",
            "stats_orders_with_affiliates": 321,
            "approval_status": "active",
            "approval_status_message": None,
            "vendor_name": "Example Vendor",
            "affiliate_support_url": "https://vendor.example.test/affiliates",
            "product_created_at": None,
            "stats_updated_at": None,
        }],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle(route):
                request = route.request
                if request.url.endswith("/api/auth/me"):
                    _fulfill(route, {
                        "authenticated": True,
                        "user": {"email": "publisher@example.test"},
                        "csrf_token": "browser-test",
                    })
                elif request.method == "GET" and request.url.endswith("/api/provider-connections"):
                    _fulfill(route, {"data": connections})
                elif request.method == "POST" and request.url.endswith("/api/provider-connections/digistore24"):
                    seen["connect"] = json.loads(request.post_data or "{}")
                    connections[:] = [row]
                    _fulfill(route, row, 201)
                elif request.method == "POST" and request.url.endswith("/api/provider-connections/ds-1/digistore24/test"):
                    _fulfill(route, row)
                elif request.method == "POST" and request.url.endswith("/api/provider-connections/ds-1/digistore24/marketplace/search"):
                    seen["search"] = json.loads(request.post_data or "{}")
                    _fulfill(route, report)
                elif request.method == "GET" and "/api/provider-connections/ds-1/digistore24/marketplace" in request.url:
                    _fulfill(route, {**report, "count": 1, "limit": 50, "offset": 0})
                elif request.method == "DELETE" and request.url.endswith("/api/provider-connections/ds-1"):
                    seen["disconnect"] = True
                    connections.clear()
                    _fulfill(route, {"id": "ds-1", "provider_id": "digistore24", "status": "disconnected"})
                else:
                    _fulfill(route, {})

            page.route("**/api/**", handle)
            page.goto(f"{BASE_URL}/integrations", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Connect Digistore24").wait_for(state="visible")
            page.get_by_label("Digistore24 read-only API key").fill(API_KEY)
            page.get_by_role("button", name="Verify & connect Digistore24").click()
            page.get_by_test_id("provider-connection-ds-1").wait_for(state="visible")
            assert seen["connect"] == {"api_key": API_KEY}

            page.get_by_label("Search Digistore24 marketplace").fill("marketing")
            page.get_by_role("button", name="Search Digistore24 marketplace").click()
            page.get_by_test_id("digistore24-marketplace-results").wait_for(state="visible")
            assert seen["search"] == {"query": "marketing", "limit": 50}
            assert page.get_by_text("Practical AI Marketing Course").is_visible()
            assert page.get_by_text("EUR 79.0").is_visible()
            assert page.get_by_text("Affiliate share (provider value): 50").is_visible()
            assert page.get_by_text("Not an accepted partnership:").is_visible()

            page.get_by_role("button", name="Load saved Digistore24 marketplace").click()
            page.get_by_text("Practical AI Marketing Course").wait_for(state="visible")
            page.get_by_role("button", name="Disconnect").click()
            assert seen["disconnect"] is True
        finally:
            browser.close()
