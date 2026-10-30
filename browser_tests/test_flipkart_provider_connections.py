from __future__ import annotations

import json
import os
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")
TRACKING_ID = "creator123"
API_TOKEN = "private-flipkart-token-" + "x" * 32


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


def test_flipkart_connect_search_products_load_offers_and_disconnect():
    connections = []
    seen = {"product_search": None, "offers": 0, "disconnect": 0}

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
                elif request.method == "POST" and request.url.endswith("/api/provider-connections/flipkart"):
                    payload = json.loads(request.post_data or "{}")
                    assert payload == {"tracking_id": TRACKING_ID, "api_token": API_TOKEN}
                    row = {
                        "id": "fk-1",
                        "provider_id": "flipkart",
                        "status": "connected_read_only",
                        "account_nicknames": [TRACKING_ID],
                        "capabilities": ["product_feed.directory.read", "products.search", "offers.list"],
                        "permissions_verified": ["Product Feed Directory", "Product Search", "Active Offers"],
                        "credential_present": True,
                        "last_checked_at": "2026-10-30T12:00:00+00:00",
                        "last_error_code": None,
                        "created_at": None,
                        "categories": ["api", "api_v1"],
                    }
                    connections[:] = [{key: value for key, value in row.items() if key != "categories"}]
                    _fulfill(route, row, 201)
                elif request.method == "POST" and request.url.endswith("/api/provider-connections/fk-1/flipkart/test"):
                    _fulfill(route, {
                        **connections[0],
                        "categories": ["api", "api_v1"],
                    })
                elif request.method == "POST" and request.url.endswith("/api/provider-connections/fk-1/flipkart/products/search"):
                    payload = json.loads(request.post_data or "{}")
                    seen["product_search"] = payload
                    _fulfill(route, {
                        "provider_id": "flipkart",
                        "evidence_type": "provider_reported_product_search",
                        "source_endpoint": "affiliate/1.0/search.json",
                        "query": payload["query"],
                        "requested_count": payload["result_count"],
                        "result_count": 1,
                        "persisted_count": 1,
                        "source_checked_at": "2026-10-30T12:00:00+00:00",
                        "commission_terms_status": "not_exposed_by_product_search_endpoint",
                        "note": "Provider product data only. Commission rate, cookie duration, payout terms, account eligibility and promotion approval were not supplied.",
                        "products": [{
                            "external_id": "MOBABC123",
                            "title": "Sample Android Phone",
                            "description": "Provider supplied description",
                            "brand": "ExampleBrand",
                            "category": "Mobiles / Smartphones",
                            "product_url": "https://www.flipkart.com/sample-phone",
                            "image_url": "https://rukminim1.flixcart.com/sample.jpeg",
                            "price_amount": "12999",
                            "mrp_amount": "15999",
                            "currency": "INR",
                            "in_stock": True,
                            "discount_percentage": "18",
                        }],
                    })
                elif request.method == "GET" and "/api/provider-connections/fk-1/flipkart/offers" in request.url:
                    seen["offers"] += 1
                    _fulfill(route, {
                        "provider_id": "flipkart",
                        "evidence_type": "provider_reported_active_offers",
                        "source_endpoint": "affiliate/offers/v1/all/json",
                        "offer_kind": "all",
                        "result_count": 1,
                        "persisted_count": 1,
                        "source_checked_at": "2026-10-30T12:01:00+00:00",
                        "commission_terms_status": "not_exposed_by_offer_feed",
                        "note": "Offer feed contains no commission rate or cookie duration; these remain unknown.",
                        "offers": [{
                            "external_id": "offer-1",
                            "title": "Weekend electronics offer",
                            "description": "Provider supplied offer details",
                            "category": "Electronics",
                            "offer_url": "https://www.flipkart.com/offers/sample",
                            "image_url": None,
                            "availability_status": "LIVE",
                            "is_available": True,
                            "start_at": "2026-10-29T00:00:00+00:00",
                            "end_at": "2026-11-02T23:59:59+00:00",
                        }],
                    })
                elif request.method == "DELETE" and request.url.endswith("/api/provider-connections/fk-1"):
                    seen["disconnect"] += 1
                    connections[0]["status"] = "disconnected"
                    connections[0]["credential_present"] = False
                    _fulfill(route, {
                        "id": "fk-1",
                        "provider_id": "flipkart",
                        "status": "disconnected",
                        "credential_present": False,
                        "provider_key_revoked_remotely": False,
                        "detail": "Saved credential removed from OmniAffiliateOS. Revoke or regenerate it separately in Flipkart Affiliate API settings.",
                    })
                else:
                    _fulfill(route, {"detail": "Unexpected request: " + request.method + " " + request.url}, 404)

            page.route("**/api/**", handle)
            page.goto(BASE_URL + "/integrations", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Affiliate account connections").wait_for(state="visible")

            page.get_by_label("Affiliate tracking ID").fill(TRACKING_ID)
            page.get_by_label("Private Affiliate API token").fill(API_TOKEN)
            page.get_by_role("button", name="Verify & connect Flipkart").click()
            page.get_by_test_id("flipkart-provider-tools").wait_for(state="visible")
            assert page.get_by_label("Private Affiliate API token").input_value() == ""
            assert API_TOKEN not in page.locator("main").inner_text()
            assert page.get_by_text(TRACKING_ID, exact=True).is_visible()
            assert page.get_by_text("Product Search", exact=False).is_visible()

            page.get_by_role("button", name="Search Flipkart products").click()
            page.get_by_test_id("flipkart-product-results").wait_for(state="visible")
            assert seen["product_search"] == {"query": "mobile phone", "result_count": 10}
            assert page.get_by_text("Sample Android Phone", exact=True).is_visible()
            assert page.get_by_text("INR 12999", exact=True).is_visible()
            assert page.get_by_text("Commission rate, cookie duration", exact=False).is_visible()

            page.get_by_role("button", name="Load active offers").click()
            page.get_by_test_id("flipkart-active-offers").wait_for(state="visible")
            assert page.get_by_text("Weekend electronics offer", exact=True).is_visible()
            assert seen["offers"] == 1

            page.get_by_role("button", name="Test connection").click()
            page.get_by_text("Flipkart affiliate API directory verification passed.", exact=True).wait_for(state="visible")
            page.get_by_role("button", name="Disconnect").click()
            page.get_by_text("Revoke or regenerate it separately in Flipkart Affiliate API settings.", exact=False).wait_for(state="visible")
            assert seen["disconnect"] == 1
            assert connections[0]["credential_present"] is False
        finally:
            browser.close()
