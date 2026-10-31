from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def test_connected_affiliate_marketplace_research_runs_single_workspace_search():
    requests = []
    response = {
        "query": "creator tools", "status": "provider_reported", "result_count": 2,
        "results": [
            {"provider_id": "digistore24", "connection_id": "connection-ds24", "account_reference": "123456",
             "external_id": "12345", "title": "Ethical AI Marketing Course", "description": "Provider supplied description.",
             "category": "Education", "vendor": "Example Vendor", "product_url": "https://vendor.example.test/course",
             "price_amount": "79.0", "currency": "EUR", "availability_status": "active",
             "commission_terms_status": "provider_marketplace_fields_only", "source_endpoint": "listMarketplaceEntries",
             "source_checked_at": "2026-10-31T07:00:00+00:00"},
            {"provider_id": "flipkart", "connection_id": "connection-flipkart", "account_reference": "tracking-123",
             "external_id": "FK-123", "title": "Creator Video Camera", "description": "Provider supplied description.",
             "category": "Electronics", "vendor": "Example Brand", "product_url": "https://www.flipkart.com/item/p/itm123",
             "price_amount": "1999.00", "currency": "INR", "availability_status": "IN_STOCK",
             "commission_terms_status": "not_exposed_by_product_search_endpoint", "source_endpoint": "affiliate/1.0/search.json",
             "source_checked_at": "2026-10-31T07:00:00+00:00"},
        ],
        "providers": [
            {"provider_id": "digistore24", "status": "provider_reported", "connected_accounts_found": 1, "accounts_searched": 1, "result_count": 1, "persisted_count": 1, "errors": []},
            {"provider_id": "flipkart", "status": "provider_reported", "connected_accounts_found": 1, "accounts_searched": 1, "result_count": 1, "persisted_count": 1, "errors": []},
        ],
        "execution": {"provider_api_calls": 2, "external_writes_executed": False, "affiliate_applications_submitted": False,
                      "content_published": False, "ad_spend_changed": False, "payouts_transferred": False},
        "disclaimer": "Provider-reported only; terms and earnings are not independently verified.",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_search(route):
                requests.append({"method": route.request.method, "body": route.request.post_data_json})
                route.fulfill(status=200, content_type="application/json", body=json.dumps(response))

            page.route("**/api/affiliate-research/search", handle_search)
            page.goto(f"{BASE_URL}/affiliate-research", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Affiliate marketplace research").wait_for(state="visible")
            page.get_by_label("Niche or product search").fill("creator tools")
            page.get_by_role("button", name="Search connected accounts").click()
            page.get_by_role("heading", name="Ethical AI Marketing Course").wait_for(state="visible")
            page.get_by_role("heading", name="Creator Video Camera").wait_for(state="visible")
            result_cards = page.locator('section[aria-label="Marketplace research results"] article')
            assert result_cards.count() == 2
            assert result_cards.filter(has_text="Not independently verified").count() == 2
            assert result_cards.filter(has_text="Cookie / attribution").count() == 2
            assert len(requests) == 1
            assert requests[0] == {"method": "POST", "body": {"query": "creator tools", "limit": 10}}
            assert "provider-reported" in page.locator("main").inner_text().lower()
        finally:
            browser.close()
