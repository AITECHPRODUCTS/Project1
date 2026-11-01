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
            assert not page.get_by_label("I'm a partner").is_checked()
            assert not page.get_by_label("I'm a brand").is_checked()
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
            page.get_by_label("I'm a brand").check(force=True)
            page.get_by_label("Email address").fill("merchant@example.test")
            page.get_by_label("Password").fill("MerchantStrongPassword123")
            page.get_by_role("button", name="Create account").click()
            page.wait_for_url("**/dashboard")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")
            assert page.get_by_text("Brand / Merchant workspace").is_visible()
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


def test_merchant_opening_publisher_url_returns_to_the_shared_dashboard():
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
                            "email": "merchant@example.test",
                            "account_type": "merchant_product_owner",
                            "is_admin": False,
                            "workspace_role": "owner",
                        },
                    })
                elif path.endswith("/api/workspaces"):
                    _json(route, {"active_workspace_id": "merchant-workspace", "data": []})
                elif path.endswith("/api/merchant/offers"):
                    _json(route, {"count": 0, "data": []})
                elif path.endswith("/api/merchant/applications"):
                    _json(route, {"count": 0, "total_count": 0, "data": []})
                else:
                    _json(route, {"detail": "Unexpected request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/publisher", wait_until="domcontentloaded")
            page.wait_for_url("**/dashboard")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")
            assert page.get_by_text("Brand / Merchant workspace").is_visible()
        finally:
            browser.close()


def test_publisher_opening_merchant_url_returns_to_the_shared_dashboard():
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
                elif path.endswith("/api/workspaces"):
                    _json(route, {"active_workspace_id": "publisher-workspace", "data": []})
                elif path.endswith("/api/status"):
                    _json(route, {"clicks": 0, "conversion_events": 0})
                elif path.endswith("/api/marketplace/offers"):
                    _json(route, {"count": 0, "data": []})
                elif path.endswith("/api/marketplace/applications"):
                    _json(route, {"count": 0, "total_count": 0, "data": []})
                elif path.endswith("/api/campaigns"):
                    _json(route, {"count": 0, "data": []})
                else:
                    _json(route, {"detail": "Unexpected request"}, 404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/merchant", wait_until="domcontentloaded")
            page.wait_for_url("**/dashboard")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")
            assert page.get_by_text("Affiliate / Partner workspace").is_visible()
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
            page.get_by_label("I'm a partner").check(force=True)
            page.get_by_label("Email address").fill("publisher@example.test")
            page.get_by_label("Password").fill("PublisherStrongPassword123")
            page.get_by_role("button", name="Create account").click()
            page.wait_for_url("**/dashboard")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")
            assert page.get_by_text("Affiliate / Partner workspace").is_visible()
            assert ("POST", "http://127.0.0.1:8000/api/auth/register") in calls
            assert any(path.endswith("/api/marketplace/offers") for _, path in calls)
        finally:
            browser.close()

def test_public_homepage_query_does_not_open_the_legacy_growth_workspace():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            api_calls = []
            page.route("**/api/**", lambda route: (api_calls.append(route.request.url), _json(route, {"detail": "No API call expected"}, 401)))
            page.goto(BASE_URL + "/?view=content-studio", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Grow through partnerships.").wait_for(state="visible")
            assert page.locator("main").get_attribute("data-current-view") is None
            assert api_calls == []
        finally:
            browser.close()



def test_platform_admin_legacy_business_urls_return_to_protected_admin_console():
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
            page.wait_for_url("**/admin")
            page.get_by_role("heading", name="Tenant lifecycle console").wait_for(state="visible")
            page.goto(BASE_URL + "/merchant", wait_until="domcontentloaded")
            page.wait_for_url("**/admin")
            page.get_by_role("heading", name="Tenant lifecycle console").wait_for(state="visible")
            assert not any("/api/merchant/" in url for url in requests)
            assert not any("/api/marketplace/" in url for url in requests)
            assert not any(url.endswith("/api/status") for url in requests)
        finally:
            browser.close()


def test_publisher_workspace_navigation_has_home_and_grouped_feature_links():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def respond(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {"user": {"email": "publisher@example.test", "account_type": "affiliate_publisher", "is_admin": False, "workspace_id": "workspace-1", "workspace_role": "owner"}})
                elif path.endswith("/api/workspaces"):
                    _json(route, {"active_workspace_id": "workspace-1", "data": [{"id": "workspace-1", "name": "Publisher workspace", "role": "owner", "lifecycle_state": "active", "is_active": True}]})
                elif path.endswith("/api/status"):
                    _json(route, {"clicks": 12, "conversion_events": 3})
                elif path.endswith("/api/marketplace/offers"):
                    _json(route, {"count": 4, "data": [{}, {}, {}, {}]})
                elif path.endswith("/api/marketplace/applications"):
                    _json(route, {"count": 1, "total_count": 1, "data": [{}]})
                elif path.endswith("/api/campaigns"):
                    _json(route, {"count": 2, "data": [{}, {}]})
                else:
                    _json(route, {})
            page.route("**/api/**", respond)
            page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")

            navigation = page.get_by_role("navigation", name="Primary workspace navigation")
            assert navigation.get_by_role("link", name="Home").get_attribute("href") == "/"
            assert navigation.get_by_role("link", name="Workspace overview").get_attribute("href") == "/dashboard"

            research_group = navigation.locator("details").filter(has_text="Discover & Research")
            research_group.locator("summary").click()
            assert research_group.get_by_role("link", name="Publisher marketplace").get_attribute("href") == "/marketplace"
            assert research_group.get_by_role("link", name="Affiliate offer catalog").get_attribute("href") == "/offers"

            assert navigation.get_by_role("link", name="Platform administration").count() == 0
        finally:
            browser.close()


def test_merchant_workspace_navigation_only_exposes_merchant_program_tools():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def respond(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {"user": {"email": "merchant@example.test", "account_type": "merchant_product_owner", "is_admin": False, "workspace_id": "workspace-2", "workspace_role": "owner"}})
                elif path.endswith("/api/workspaces"):
                    _json(route, {"active_workspace_id": "workspace-2", "data": [{"id": "workspace-2", "name": "Brand workspace", "role": "owner", "lifecycle_state": "active", "is_active": True}]})
                elif path.endswith("/api/merchant/offers"):
                    _json(route, {"count": 0, "data": []})
                elif path.endswith("/api/merchant/applications"):
                    _json(route, {"count": 0, "total_count": 0, "data": []})
                else:
                    _json(route, {})
            page.route("**/api/**", respond)
            page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")

            navigation = page.get_by_role("navigation", name="Primary workspace navigation")
            assert navigation.get_by_role("link", name="Workspace overview").get_attribute("href") == "/dashboard"
            program_group = navigation.locator("details").filter(has_text="Program management")
            program_group.locator("summary").click()
            assert program_group.get_by_role("link", name="Manage offers").get_attribute("href") == "/merchant/offers"
            assert program_group.get_by_role("link", name="Partner applications").get_attribute("href") == "/merchant/applications"
            assert navigation.get_by_role("link", name="Affiliate offer catalog").count() == 0
        finally:
            browser.close()


def test_growth_studio_does_not_request_super_admin_capabilities_for_publishers():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            capability_requests = []

            def respond(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {"user": {"email": "publisher@example.test", "account_type": "affiliate_publisher", "is_admin": False, "workspace_id": "workspace-1", "workspace_role": "owner"}})
                elif path.endswith("/api/workspaces"):
                    _json(route, {"active_workspace_id": "workspace-1", "data": []})
                elif path.endswith("/api/status"):
                    _json(route, {"app_name": "OmniAffiliateOS", "environment": "development", "execution_mode": "SEMI_AUTONOMOUS", "clicks": 0, "conversion_events": 0, "commission_recorded": 0})
                elif path.endswith("/api/resource-budget"):
                    _json(route, {"daily_budget_usd": 0, "daily_estimated_used_usd": 0, "daily_estimated_remaining_usd": 0, "niche_budget_usd": 0, "note": "No budget data"})
                elif path.endswith("/api/integrations"):
                    _json(route, {"total": 0, "counts": {}, "items": [], "verification_policy": "workspace scoped"})
                elif path.endswith("/api/capabilities"):
                    capability_requests.append(path)
                    _json(route, {"detail": "Platform Super Admin permission required"}, 403)
                else:
                    _json(route, {})
            page.route("**/api/**", respond)
            page.goto(BASE_URL + "/growth", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Growth Studio", exact=False).wait_for(state="visible")
            assert capability_requests == []
            assert page.get_by_text("403: Platform Super Admin permission required", exact=True).count() == 0
            assert page.get_by_text("Automation & Governance", exact=True).count() >= 1
        finally:
            browser.close()


def test_non_admin_visiting_platform_console_is_returned_to_own_workspace():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def respond(route):
                path = route.request.url.split("?", 1)[0]
                if path.endswith("/api/auth/me"):
                    _json(route, {"user": {"email": "publisher@example.test", "account_type": "affiliate_publisher", "is_admin": False, "workspace_id": "workspace-1", "workspace_role": "owner"}})
                elif path.endswith("/api/workspaces"):
                    _json(route, {"active_workspace_id": "workspace-1", "data": []})
                elif path.endswith("/api/status"):
                    _json(route, {"clicks": 0, "conversion_events": 0})
                elif path.endswith("/api/marketplace/offers") or path.endswith("/api/marketplace/applications") or path.endswith("/api/campaigns"):
                    _json(route, {"count": 0, "total_count": 0, "data": []})
                else:
                    _json(route, {})
            page.route("**/api/**", respond)
            page.goto(BASE_URL + "/admin", wait_until="domcontentloaded")
            page.wait_for_url("**/dashboard")
            page.get_by_role("heading", name="Your workspace, at a glance.").wait_for(state="visible")
            assert page.get_by_text("Platform administrator access required", exact=True).count() == 0
        finally:
            browser.close()
