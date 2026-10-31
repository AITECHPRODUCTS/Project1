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


def test_merchant_dashboard_uses_workspace_offer_and_application_data():
    offers = {
        "count": 4,
        "data": [
            {
                "id": "offer-draft-1",
                "name": "Draft analytics course",
                "status": "draft",
                "affiliate_network_approval_status": "not_submitted",
                "affiliate_network_approved": False,
                "created_at": "2026-10-30T08:00:00+00:00",
            },
            {
                "id": "offer-review-1",
                "name": "Creator toolkit",
                "status": "submitted_for_review",
                "affiliate_network_approval_status": "pending",
                "affiliate_network_approved": False,
                "created_at": "2026-10-29T08:00:00+00:00",
            },
            {
                "id": "offer-approved-1",
                "name": "Approved writing platform",
                "status": "approved",
                "affiliate_network_approval_status": "approved",
                "affiliate_network_approved": True,
                "created_at": "2026-10-28T08:00:00+00:00",
            },
            {
                "id": "offer-internal-only",
                "name": "Merchant-approved course",
                "status": "approved",
                "affiliate_network_approval_status": "pending",
                "affiliate_network_approved": False,
                "created_at": "2026-10-27T08:00:00+00:00",
            },
        ],
    }
    pending_applications = {
        "count": 1,
        "total_count": 4,
        "limit": 1,
        "offset": 0,
        "status_filter": "pending_review",
        "data": [],
    }
    requests: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                url = route.request.url
                requests.append(url)
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {"authenticated": True, "user": {"email": "merchant@example.test", "account_type": "merchant_product_owner", "is_admin": False}})
                    return
                if "/api/merchant/offers?" in url:
                    _fulfill_json(route, offers)
                    return
                if "/api/merchant/applications?" in url:
                    _fulfill_json(route, pending_applications)
                    return
                _fulfill_json(route, {"detail": "Unexpected request"}, status=404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/merchant", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Merchant workspace").wait_for(state="visible")

            assert page.get_by_test_id("merchant-stat-offers").inner_text() == "4"
            assert page.get_by_test_id("merchant-stat-drafts").inner_text() == "1"
            assert page.get_by_test_id("merchant-stat-review").inner_text() == "1"
            assert page.get_by_test_id("merchant-stat-applications").inner_text() == "4"
            assert page.get_by_test_id("merchant-stat-internal-approved").inner_text() == "2"
            assert page.get_by_test_id("merchant-stat-network-approved").inner_text() == "1"
            assert page.get_by_text("Internal merchant status: submitted for review").is_visible()
            pending_network_status = page.get_by_text("Affiliate-network status: pending", exact=True)
            assert pending_network_status.count() == 2
            assert pending_network_status.first.is_visible()
            assert page.get_by_role("link", name="Manage offers").is_visible()
            assert page.get_by_role("link", name="Review applications").is_visible()
            assert any("/api/merchant/offers?" in url for url in requests)
            assert any("/api/merchant/applications?" in url for url in requests)
            assert "does not infer network approval" in page.locator("main").inner_text()
            merchant_nav = page.get_by_role("navigation", name="Merchant dashboard navigation")
            assert merchant_nav.get_by_role("link", name="Dashboard").get_attribute("href") == "/merchant"
            assert merchant_nav.get_by_role("link", name="Manage offers").get_attribute("href") == "/merchant/offers"
            assert merchant_nav.get_by_role("link", name="Review applications").get_attribute("href") == "/merchant/applications"
            assert page.get_by_role("button", name="Refresh workspace").is_visible()
        finally:
            browser.close()


def test_merchant_subpages_link_back_to_dashboard():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                url = route.request.url
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {"authenticated": True, "user": {"email": "merchant@example.test", "account_type": "merchant_product_owner", "is_admin": False}})
                elif "/api/merchant/offers" in url:
                    _fulfill_json(route, {"count": 0, "data": []})
                elif "/api/merchant/applications" in url:
                    _fulfill_json(route, {
                        "count": 0, "total_count": 0, "limit": 25, "offset": 0,
                        "status_filter": "all", "data": [],
                    })
                else:
                    _fulfill_json(route, {"detail": "Unexpected request"}, status=404)

            page.route("**/api/**", handle_api)
            for path, heading in (
                ("/merchant/offers", "Merchant offers"),
                ("/merchant/applications", "Publisher applications"),
            ):
                page.goto(BASE_URL + path, wait_until="domcontentloaded")
                page.get_by_role("heading", name=heading).wait_for(state="visible")
                dashboard_link = page.get_by_role("link", name="Merchant dashboard")
                assert dashboard_link.is_visible()
                assert dashboard_link.get_attribute("href") == "/merchant"
        finally:
            browser.close()


def test_merchant_dashboard_surfaces_workspace_authorization_errors():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                url = route.request.url
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {"authenticated": True, "user": {"email": "merchant@example.test", "account_type": "merchant_product_owner", "is_admin": False}})
                    return
                if "/api/merchant/offers?" in url:
                    _fulfill_json(route, {"count": 0, "data": []})
                    return
                if "/api/merchant/applications?" in url:
                    _fulfill_json(route, {"detail": "Merchant owner/admin access required"}, status=403)
                    return
                _fulfill_json(route, {"detail": "Unexpected request"}, status=404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/merchant", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Merchant workspace").wait_for(state="visible")
            page.locator("main [role=alert]").wait_for(state="visible")
            assert "403" in page.locator("main [role=alert]").inner_text()
            assert page.get_by_role("button", name="Retry").is_visible()
        finally:
            browser.close()
