from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def test_publisher_program_detail_shows_supported_data_and_marks_missing_surfaces():
    detail = {
        "id": "application-active-1",
        "merchant_offer_id": "offer-1",
        "offer_name": "Creator Analytics Suite",
        "status": "approved",
        "created_at": "2026-10-20T10:00:00+00:00",
        "reviewed_at": "2026-10-21T10:00:00+00:00",
        "reviewer_notes": "Approved for organic content and newsletter traffic.",
        "terms_snapshot": {
            "category": "analytics",
            "commission_type": "recurring_percentage",
            "commission_value": "25.0000",
            "commission_currency": "USD",
            "cookie_days": 30,
            "attribution_window_days": 30,
            "refund_hold_days": 15,
            "minimum_payout_amount": "50.00",
            "payout_schedule": "monthly",
            "terms_version": "terms-2026-10",
            "allowed_regions": ["US", "GB"],
            "restricted_traffic_sources": ["incentivized"],
            "affiliate_disclosure": "Readers must be told when the publisher may earn a commission.",
        },
        "provider_submission_status": "not_configured",
        "affiliate_network_approved": False,
        "promotion_url": "https://omni.example.test/r/campaign-1",
        "promotion_link_status": "active",
        "promotion_campaign_id": "campaign-1",
        "links": [{
            "id": "link-primary-1",
            "label": "Primary link",
            "destination_url": "https://omni.example.test/product",
            "campaign_id": "campaign-1",
            "promotion_url": "https://omni.example.test/r/campaign-1",
            "status": "active",
            "is_primary": True,
            "clicks_all_time": 42,
            "conversion_entries": 1,
        }],
        "tracked_clicks": 42,
        "commission_observations": [{
            "currency": "USD",
            "evidence_status": "merchant_signed_webhook_verified",
            "entry_type": "conversion",
            "entry_count": "1",
            "commission_total": "25.000000",
            "revenue_total": "100.000000",
        }],
        "performance": {
            "clicks_all_time": 42,
            "clicks_last_30_days": 7,
            "clicks_by_day": [{"date": "2026-10-31", "clicks": 7}],
            "conversion_entries": 1,
        },
        "performance_note": "First-party click records and webhook evidence only.",
        "earnings_note": "Signed merchant events are commission observations, not proof of payout or funds received.",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                path = urlparse(route.request.url).path
                if path == "/api/auth/me":
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({
                            "authenticated": True,
                            "user": {
                                "email": "publisher@example.test",
                                "account_type": "affiliate_publisher",
                                "is_admin": False,
                            },
                            "csrf_token": "browser-test-token",
                        }),
                    )
                    return
                if path == "/api/marketplace/applications/application-active-1/links" and route.request.method == "POST":
                    payload = json.loads(route.request.post_data or "{}")
                    created = {
                        "id": "link-secondary-1",
                        "label": payload["label"],
                        "destination_url": payload.get("destination_url") or "https://omni.example.test/product",
                        "campaign_id": "campaign-2",
                        "promotion_url": "https://omni.example.test/r/campaign-2",
                        "status": "active",
                        "is_primary": False,
                        "clicks_all_time": 0,
                        "conversion_entries": 0,
                    }
                    detail["links"].append(created)
                    route.fulfill(status=201, content_type="application/json", body=json.dumps(created))
                    return
                if path == "/api/marketplace/applications/application-active-1":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(detail))
                    return
                route.fulfill(status=404, content_type="application/json", body='{"detail":"Unexpected request"}')

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/programs/application-active-1", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Creator Analytics Suite").wait_for(state="visible")
            page.get_by_text("Clicks · 30 days", exact=True).wait_for(state="visible")
            assert page.get_by_text("25.000000 USD", exact=True).count() == 0

            page.get_by_role("button", name="Links").click()
            page.get_by_text("Primary link · primary", exact=True).wait_for(state="visible")
            assert page.get_by_text("https://omni.example.test/r/campaign-1", exact=True).is_visible()
            page.get_by_role("button", name="Create tracked link").click()
            page.get_by_text("Social profile link", exact=True).wait_for(state="visible")
            page.get_by_text("2 / 20 links", exact=True).wait_for(state="visible")
            assert page.get_by_text("https://omni.example.test/r/campaign-2", exact=True).is_visible()

            page.get_by_role("button", name="Commissions").click()
            page.get_by_text("Merchant Signed Webhook Verified", exact=True).wait_for(state="visible")
            page.get_by_text("25.000000 USD", exact=True).wait_for(state="visible")

            page.get_by_role("button", name="Terms").click()
            page.get_by_text("Readers must be told when the publisher may earn a commission.", exact=False).wait_for(state="visible")

            page.get_by_role("button", name="Customers · not available").click()
            page.get_by_role("heading", name="Referred customers").wait_for(state="visible")
            page.get_by_text("Not implemented", exact=True).wait_for(state="visible")

            page.get_by_role("button", name="Messages", exact=True).click()
            page.get_by_role("heading", name="Merchant–partner conversation").wait_for(state="visible")
            message_link = page.get_by_role("link", name="Open program messages")
            assert message_link.get_attribute("href") == "/messages?applicationId=application-active-1"

            page.get_by_role("button", name="Payouts · not available").click()
            page.get_by_role("heading", name="Payout account and withdrawal history").wait_for(state="visible")
        finally:
            browser.close()
