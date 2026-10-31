from __future__ import annotations

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:3100"


def _json(route, payload, status=200):
    import json
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def test_registration_page_requires_an_explicit_single_persona():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/**", lambda route: _json(route, {"detail": "Authentication required"}, 401))
            page.goto(BASE_URL + "/register", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Create your account").wait_for(state="visible")
            submit = page.get_by_role("button", name="Create account")
            assert submit.is_disabled()
            assert not page.get_by_label("Affiliate / Publisher").is_checked()
            assert not page.get_by_label("Merchant / Product Owner").is_checked()
        finally:
            browser.close()


def test_merchant_registration_redirects_to_merchant_dashboard():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            registered = {"done": False}
            calls = []

            def handle_api(route):
                request = route.request
                path = request.url.split("?", 1)[0]
                calls.append((request.method, path))
                if path.endswith("/api/auth/me"):
                    if registered["done"]:
                        _json(route, {
                            "authenticated": True,
                            "csrf_token": "merchant-persona-csrf",
                            "user": {
                                "email": "merchant@example.test",
                                "account_type": "merchant_product_owner",
                                "is_admin": False,
                                "workspace_role": "owner",
                            },
                        })
                    else:
                        _json(route, {"detail": "Authentication required"}, 401)
                elif path.endswith("/api/auth/register") and request.method == "POST":
                    payload = request.post_data_json
                    assert payload["account_type"] == "merchant_product_owner"
                    registered["done"] = True
                    _json(route, {
                        "authenticated": True,
                        "csrf_token": "merchant-persona-csrf",
                        "user": {
                            "email": payload["email"],
                            "account_type": payload["account_type"],
                            "is_admin": False,
                            "workspace_role": "owner",
                        },
                    }, 201)
                elif path.endswith("/api/merchant/offers"):
                    _json(route, {"count": 0, "data": []})
                elif path.endswith("/api/merchant/applications"):
                    _json(route, {"count": 0, "total_count": 0, "limit": 1, "offset": 0, "data": []})
                else:
                    _json(route, {"detail": "Unexpected API request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/register", wait_until="domcontentloaded")
            page.get_by_label("Merchant / Product Owner").check(force=True)
            page.get_by_label("Email address").fill("merchant@example.test")
            page.get_by_label("Password").fill("MerchantStrongPassword123")
            page.get_by_role("button", name="Create account").click()
            page.wait_for_url("**/merchant")
            page.get_by_role("heading", name="Merchant workspace").wait_for(state="visible")
            assert ("POST", "http://127.0.0.1:8000/api/auth/register") in calls
            assert any(path.endswith("/api/merchant/offers") for _, path in calls)
        finally:
            browser.close()


def test_publisher_dashboard_uses_publisher_identity_and_persisted_counts():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "publisher@example.test",
                            "account_type": "affiliate_publisher",
                            "is_admin": False,
                            "workspace_role": "owner",
                        },
                    })
                elif path.endswith("/api/status"):
                    _json(route, {"clicks": 12, "conversion_events": 3, "commission_recorded": 42.5})
                elif path.endswith("/api/marketplace/offers"):
                    _json(route, {"count": 4, "data": [{}, {}, {}, {}]})
                elif path.endswith("/api/marketplace/applications"):
                    _json(route, {
                        "count": 2,
                        "total_count": 2,
                        "data": [
                            {"id": "publisher-app-1", "offer_name": "Creator toolkit", "status": "pending_review", "created_at": "2026-10-30T08:00:00+00:00", "reviewer_notes": None},
                            {"id": "publisher-app-2", "offer_name": "Video platform", "status": "approved", "created_at": "2026-10-29T08:00:00+00:00", "reviewer_notes": "Approved internally"},
                        ],
                    })
                elif path.endswith("/api/campaigns"):
                    _json(route, {"count": 1, "data": [{}]})
                elif path.endswith("/api/finance/conversion-ledger"):
                    _json(route, {
                        "returned_count": 2,
                        "total_entry_count": 2,
                        "limit": 500,
                        "read_only": True,
                        "totals_by_currency_and_evidence": [
                            {"currency": "USD", "evidence_status": "provider_reported_unreconciled", "entry_count": 1, "commission_total": "12.500000", "revenue_total": "50.000000"},
                            {"currency": "INR", "evidence_status": "matched_click", "entry_count": 1, "commission_total": "240.000000", "revenue_total": "1200.000000"},
                        ],
                        "data": [{
                            "id": "commission-evidence-1", "network": "ClickBank",
                            "external_event_id": "order-1", "click_id": "click-1",
                            "entry_type": "commission", "commission_amount": "12.500000",
                            "revenue_amount": "50.000000", "currency": "USD",
                            "status": "provisional", "evidence_status": "provider_reported_unreconciled",
                            "created_at": "2026-10-30T08:00:00+00:00",
                        }],
                    })
                else:
                    _json(route, {"detail": "Unexpected API request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/publisher", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Publisher workspace").wait_for(state="visible")
            assert page.get_by_text("Tracked clicks").is_visible()
            page.get_by_text("12", exact=True).wait_for(state="visible")
            assert page.get_by_role("link", name="Explore merchant offers").is_visible()
            assert page.get_by_role("link", name="Manage integrations").is_visible()
            assert page.get_by_role("heading", name="Commission evidence by currency").is_visible()
            assert page.get_by_text("USD", exact=True).is_visible()
            assert page.get_by_text("INR", exact=True).is_visible()
            assert page.get_by_test_id("publisher-commission-commission-evidence-1").is_visible()
            assert page.get_by_test_id("publisher-application-pending_review").inner_text() == "1"
            assert page.get_by_test_id("publisher-application-approved").inner_text() == "1"
            publisher_nav = page.get_by_role("navigation", name="Publisher dashboard navigation")
            assert publisher_nav.get_by_role("link", name="Publisher tools").get_attribute("href") == "#publisher-tools"
            assert publisher_nav.get_by_role("link", name="My applications").get_attribute("href") == "/marketplace#my-applications"
            assert publisher_nav.get_by_role("link", name="Campaigns").get_attribute("href") == "/campaigns"
            assert page.get_by_role("link", name="View application status").get_attribute("href") == "/marketplace#my-applications"
            assert page.get_by_role("link", name="Open article writer").get_attribute("href") == "/listicle-writer"
            assert page.get_by_role("link", name="Open content health").get_attribute("href") == "/content-decay"
            assert page.get_by_role("link", name="Create research brief").get_attribute("href") == "/research-brief"
            assert page.get_by_role("link", name="Qualify an offer").get_attribute("href") == "/offers/qualification"
        finally:
            browser.close()


def test_merchant_account_cannot_open_publisher_dashboard():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/auth/me", lambda route: _json(route, {
                "authenticated": True,
                "user": {
                    "email": "merchant@example.test",
                    "account_type": "merchant_product_owner",
                    "is_admin": False,
                },
            }))
            page.goto(BASE_URL + "/publisher", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Publisher access required").wait_for(state="visible")
        finally:
            browser.close()


def test_publisher_account_cannot_open_merchant_dashboard():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "publisher@example.test",
                            "account_type": "affiliate_publisher",
                            "is_admin": False,
                        },
                    })
                else:
                    _json(route, {"detail": "Unexpected request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/merchant", wait_until="domcontentloaded")
            page.locator("main [role=alert]").wait_for(state="visible")
            assert "only available to Merchant / Product Owner accounts" in page.locator("main [role=alert]").inner_text()
        finally:
            browser.close()

def test_publisher_registration_redirects_to_publisher_dashboard():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            registered = {"done": False}
            calls = []

            def handle_api(route):
                request = route.request
                path = request.url.split("?", 1)[0]
                calls.append((request.method, path))
                if path.endswith("/api/auth/me"):
                    if registered["done"]:
                        _json(route, {
                            "authenticated": True,
                            "csrf_token": "publisher-persona-csrf",
                            "user": {
                                "email": "publisher@example.test",
                                "account_type": "affiliate_publisher",
                                "is_admin": False,
                                "workspace_role": "owner",
                            },
                        })
                    else:
                        _json(route, {"detail": "Authentication required"}, 401)
                elif path.endswith("/api/auth/register") and request.method == "POST":
                    payload = request.post_data_json
                    assert payload["account_type"] == "affiliate_publisher"
                    registered["done"] = True
                    _json(route, {
                        "authenticated": True,
                        "csrf_token": "publisher-persona-csrf",
                        "user": {
                            "email": payload["email"],
                            "account_type": payload["account_type"],
                            "is_admin": False,
                            "workspace_role": "owner",
                        },
                    }, 201)
                elif path.endswith("/api/status"):
                    _json(route, {"clicks": 0, "conversion_events": 0, "commission_recorded": 0})
                elif path.endswith("/api/marketplace/offers"):
                    _json(route, {"count": 0, "data": []})
                elif path.endswith("/api/marketplace/applications"):
                    _json(route, {"count": 0, "total_count": 0, "data": []})
                elif path.endswith("/api/campaigns"):
                    _json(route, {"count": 0, "data": []})
                else:
                    _json(route, {"detail": "Unexpected API request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/register", wait_until="domcontentloaded")
            page.get_by_label("Affiliate / Publisher").check(force=True)
            page.get_by_label("Email address").fill("publisher@example.test")
            page.get_by_label("Password").fill("PublisherStrongPassword123")
            page.get_by_role("button", name="Create account").click()
            page.wait_for_url("**/publisher")
            page.get_by_role("heading", name="Publisher workspace").wait_for(state="visible")
            assert ("POST", "http://127.0.0.1:8000/api/auth/register") in calls
            assert any(path.endswith("/api/marketplace/offers") for _, path in calls)
        finally:
            browser.close()

def test_publisher_cannot_open_legacy_operations_dashboard_with_view_query():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "publisher@example.test",
                            "account_type": "affiliate_publisher",
                            "is_admin": False,
                            "workspace_role": "owner",
                        },
                    })
                elif path.endswith("/api/status"):
                    _json(route, {"clicks": 0, "conversion_events": 0, "commission_recorded": 0})
                elif path.endswith("/api/marketplace/offers"):
                    _json(route, {"count": 0, "data": []})
                elif path.endswith("/api/marketplace/applications"):
                    _json(route, {"count": 0, "total_count": 0, "data": []})
                elif path.endswith("/api/campaigns"):
                    _json(route, {"count": 0, "data": []})
                else:
                    _json(route, {"detail": "Unexpected API request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/?view=content-studio", wait_until="domcontentloaded")
            page.wait_for_url("**/publisher")
            page.get_by_role("heading", name="Publisher workspace").wait_for(state="visible")
            assert page.locator("main").get_attribute("data-current-view") is None
        finally:
            browser.close()



def test_platform_admin_identity_cannot_open_business_persona_dashboards():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            requests: list[str] = []

            def handle_api(route):
                requests.append(route.request.url)
                if route.request.url.endswith("/api/auth/me"):
                    _json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "operator@example.test",
                            "account_type": "platform_admin",
                            "is_admin": True,
                        },
                    })
                else:
                    _json(route, {"detail": "Forbidden"}, 403)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/publisher", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Publisher access required").wait_for(state="visible")
            page.goto(BASE_URL + "/merchant", wait_until="domcontentloaded")
            merchant_error = page.locator("main p[role='alert']")
            merchant_error.wait_for(state="visible")
            assert "only available to Merchant / Product Owner accounts" in merchant_error.inner_text()
            assert sum(url.endswith("/api/auth/me") for url in requests) == 2
            assert not any("/api/merchant/" in url for url in requests)
            assert not any("/api/status" in url for url in requests)
        finally:
            browser.close()
