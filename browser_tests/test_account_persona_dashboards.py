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
                    _json(route, {"count": 2, "total_count": 2, "data": [{}, {}]})
                elif path.endswith("/api/campaigns"):
                    _json(route, {"count": 1, "data": [{}]})
                else:
                    _json(route, {"detail": "Unexpected API request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/publisher", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Publisher workspace").wait_for(state="visible")
            assert page.get_by_text("Tracked clicks").is_visible()
            assert page.get_by_text("12", exact=True).is_visible()
            assert page.get_by_role("link", name="Explore merchant offers").is_visible()
            assert page.get_by_role("link", name="Manage integrations").is_visible()
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
