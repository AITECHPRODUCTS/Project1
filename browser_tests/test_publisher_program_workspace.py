from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def _fulfill_json(route, payload: dict, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        headers={
            "access-control-allow-origin": "http://127.0.0.1:3100",
            "access-control-allow-credentials": "true",
        },
        body=json.dumps(payload),
    )


def test_publisher_can_search_filter_and_review_program_evidence():
    applications = {
        "count": 3,
        "data": [
            {
                "id": "application-active-1", "merchant_offer_id": "offer-1",
                "offer_name": "Creator Analytics Suite", "status": "approved",
                "created_at": "2026-10-20T10:00:00+00:00", "reviewed_at": "2026-10-21T10:00:00+00:00",
                "reviewer_notes": "Approved for organic content and newsletter traffic.",
                "terms_snapshot": {
                    "category": "analytics", "commission_type": "recurring_percentage",
                    "commission_value": "25.0000", "commission_currency": "USD",
                    "cookie_days": 30, "attribution_window_days": 30, "refund_hold_days": 15,
                    "minimum_payout_amount": "50.00", "payout_schedule": "monthly",
                    "terms_version": "terms-2026-10", "allowed_regions": ["US", "GB"],
                    "restricted_traffic_sources": ["incentivized"],
                    "commission_terms_url": "https://merchant.example.test/terms",
                },
                "provider_submission_status": "not_configured", "affiliate_network_approved": False,
                "promotion_url": "https://omni.example.test/r/campaign-1", "promotion_link_status": "active",
                "tracked_clicks": 42,
                "commission_observations": [
                    {"currency": "USD", "evidence_status": "merchant_signed_webhook_verified", "commission_total": "25.000000"}
                ],
                "earnings_note": "Signed merchant events are commission observations, not proof of payout or funds received.",
            },
            {
                "id": "application-pending-2", "merchant_offer_id": "offer-2",
                "offer_name": "Video Workflow Program", "status": "pending_review",
                "created_at": "2026-10-25T10:00:00+00:00", "reviewed_at": None, "reviewer_notes": None,
                "terms_snapshot": {
                    "category": "video", "commission_type": "fixed", "commission_value": "10.00",
                    "commission_currency": "USD", "cookie_days": 14, "attribution_window_days": 14,
                    "refund_hold_days": 30, "minimum_payout_amount": "25.00", "payout_schedule": "monthly",
                    "terms_version": "terms-2026-09", "allowed_regions": ["US"], "restricted_traffic_sources": [],
                },
                "provider_submission_status": "not_configured", "affiliate_network_approved": False,
                "promotion_url": None, "promotion_link_status": None, "tracked_clicks": 0,
                "commission_observations": [], "earnings_note": "No commission evidence recorded.",
            },
            {
                "id": "application-rejected-3", "merchant_offer_id": "offer-3",
                "offer_name": "Legacy SEO Toolkit", "status": "rejected",
                "created_at": "2026-10-10T10:00:00+00:00", "reviewed_at": "2026-10-11T10:00:00+00:00",
                "reviewer_notes": "Please revise the proposed traffic plan.",
                "terms_snapshot": {"category": "seo", "terms_version": "terms-2026-08"},
                "provider_submission_status": "not_configured", "affiliate_network_approved": False,
                "promotion_url": None, "promotion_link_status": None, "tracked_clicks": 0,
                "commission_observations": [], "earnings_note": "No commission evidence recorded.",
            },
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                url = route.request.url
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {
                        "authenticated": True,
                        "user": {"email": "publisher@example.test", "account_type": "affiliate_publisher", "is_admin": False},
                        "csrf_token": "browser-test-token",
                    })
                    return
                if route.request.method == "GET" and "/api/marketplace/applications?limit=300" in url:
                    _fulfill_json(route, applications)
                    return
                _fulfill_json(route, {"detail": "Unexpected publisher program request"}, status=404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/programs", wait_until="domcontentloaded")
            page.get_by_role("heading", name="My programs").wait_for(state="visible")
            page.get_by_role("heading", name="Creator Analytics Suite").wait_for(state="visible")
            page.locator('section[aria-label="Program summary"]').get_by_text("42", exact=True).wait_for(state="visible")
            assert page.locator('section[aria-label="Program summary"]').get_by_text("42", exact=True).is_visible()
            assert page.get_by_text("25.000000", exact=True).is_visible()
            page.get_by_text("Program terms, restrictions and approval details", exact=True).click()
            assert page.get_by_text("Not configured / not verified", exact=True).is_visible()
            assert page.get_by_text("Signed merchant events are commission observations", exact=False).is_visible()

            page.get_by_role("button", name="Pending review", exact=True).click()
            assert page.get_by_role("heading", name="Video Workflow Program").is_visible()
            assert not page.get_by_role("heading", name="Creator Analytics Suite").is_visible()

            page.get_by_role("button", name="All programs", exact=True).click()
            page.get_by_label("Search programs").fill("Legacy SEO")
            assert page.get_by_role("heading", name="Legacy SEO Toolkit").is_visible()
            assert not page.get_by_role("heading", name="Video Workflow Program").is_visible()
        finally:
            browser.close()
