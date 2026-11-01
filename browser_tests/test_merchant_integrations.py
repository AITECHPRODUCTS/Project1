from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")
ONE_TIME_SECRET = "woo-one-time-test-secret-never-real"


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


def test_merchant_can_create_and_configure_woocommerce_webhook_setup():
    offers = {
        "count": 1,
        "data": [{
            "id": "offer-woo-1",
            "name": "Merchant WooCommerce program",
            "status": "approved",
            "commission_currency": "USD",
        }],
    }
    created = {
        "id": "integration-woo-1",
        "merchant_offer_id": "offer-woo-1",
        "offer_name": "Merchant WooCommerce program",
        "provider_name": "woocommerce",
        "display_name": "Primary WooCommerce store",
        "integration_type": "woocommerce_webhook",
        "status": "pending_authorization",
        "webhook_url": "https://omni.example.test/api/webhooks/merchant-integrations/integration-woo-1",
        "secret_fingerprint": "test-fingerprint",
        "signing_secret_configured": True,
        "last_event_at": None,
        "last_error_code": None,
        "created_at": "2026-11-01T12:00:00+00:00",
        "signing_secret_once": ONE_TIME_SECRET,
        "secret_display_policy": "Displayed once in this test fixture.",
        "setup_events": ["order.created", "order.updated"],
        "setup_note": "Configure order.created and order.updated topics.",
    }
    public_integration = {
        key: value for key, value in created.items()
        if key not in {"signing_secret_once", "secret_display_policy", "setup_events", "setup_note"}
    }
    seen = {"create": None}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                request = route.request
                url = request.url
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "merchant@example.test",
                            "account_type": "merchant_product_owner",
                            "is_admin": False,
                        },
                        "csrf_token": "browser-test-token",
                    })
                    return
                if request.method == "GET" and "/api/merchant/offers?" in url:
                    _fulfill_json(route, offers)
                    return
                if request.method == "GET" and url.endswith("/api/merchant/integrations"):
                    _fulfill_json(route, {"count": 1 if seen["create"] else 0,
                                          "data": [public_integration] if seen["create"] else []})
                    return
                if request.method == "POST" and url.endswith("/api/merchant/offers/offer-woo-1/webhook-integration"):
                    seen["create"] = json.loads(request.post_data or "{}")
                    _fulfill_json(route, created, status=201)
                    return
                _fulfill_json(route, {"detail": "Unexpected merchant integration request"}, status=404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/merchant/integrations", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Checkout & conversion integrations").wait_for(state="visible")
            page.locator("#merchant-webhook-offer").select_option("offer-woo-1")
            page.locator("#merchant-provider-name").select_option("woocommerce")
            page.locator("#merchant-webhook-name").fill("Primary WooCommerce store")

            page.get_by_role("button", name="Create webhook endpoint").click()
            page.get_by_text("WooCommerce setup", exact=True).wait_for(state="visible")
            assert seen["create"] == {
                "provider_name": "woocommerce",
                "display_name": "Primary WooCommerce store",
            }
            assert page.get_by_text(ONE_TIME_SECRET, exact=True).is_visible()
            assert page.get_by_text(
                "Copy this into both WooCommerce order webhook configurations now; it is not shown again."
            ).is_visible()
            assert page.get_by_text("Order created", exact=False).is_visible()
            assert page.get_by_text("Order updated", exact=False).is_visible()
            assert page.get_by_text("omni_click_id", exact=True).first.is_visible()
            assert page.get_by_text("omni_original_order_id", exact=True).is_visible()
            assert page.get_by_text(
                "https://omni.example.test/api/webhooks/merchant-integrations/integration-woo-1",
                exact=True,
            ).first.is_visible()

            page.get_by_role("button", name="I saved it — hide secret").click()
            assert not page.get_by_text(ONE_TIME_SECRET, exact=True).is_visible()
        finally:
            browser.close()
