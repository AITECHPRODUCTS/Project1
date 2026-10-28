from __future__ import annotations

import json
import os
import uuid

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def _fulfill_json(route, payload: dict) -> None:
    route.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-credentials": "true"}, body=json.dumps(payload))


def test_skill_package_builder_supports_keyboard_navigation_and_rejects_invalid_schema_without_post():
    posted: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_packages(route):
                if route.request.method == "GET":
                    _fulfill_json(route, {"count": 0, "data": []})
                else:
                    posted.append(route.request.url)
                    _fulfill_json(route, {"count": 0, "data": []})

            page.route("**/api/skills/packages**", handle_packages)
            page.goto(f"{BASE_URL}/skills", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Governed skill packages").wait_for(state="visible")
            assert page.get_by_label("Skill ID").is_visible()
            assert page.get_by_label("Input JSON schema").is_visible()
            assert page.get_by_role("button", name="Validate and save package").is_visible()
            page.get_by_text("No packages in the active workspace yet.").wait_for(state="visible")
            assert page.locator("main [role='alert']").count() == 0

            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement?.tagName") == "A"

            page.get_by_label("Input JSON schema").fill("{")
            page.get_by_role("button", name="Validate and save package").click()
            page.locator("main [role='alert']").wait_for(state="visible")
            assert posted == []
            assert "No packages in the active workspace yet." in page.locator("main").inner_text()
        finally:
            browser.close()


def test_ad_guardrails_browser_exposes_read_only_provider_boundary():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_ads(route):
                _fulfill_json(route, {"count": 0, "data": []})

            page.route("**/api/ads/**", handle_ads)
            page.goto(f"{BASE_URL}/ads/guardrails", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Ad budget guardrails").wait_for(state="visible")
            page.get_by_text("No ad plans exist in this workspace yet.").wait_for(state="visible")
            assert page.locator("main [role='alert']").count() == 0
            text = page.locator("main").inner_text().lower()
            assert "provider execution remains disabled" in text
            assert "no ad plans exist in this workspace yet" in text
            assert page.get_by_role("button", name="Refresh").is_visible()
        finally:
            browser.close()



def test_real_registration_creates_workspace_and_authenticates_dashboard():
    api_base = "http://127.0.0.1:8000"
    email = f"browser-uat-{uuid.uuid4().hex}@example.test"
    workspace_name = f"Browser UAT {uuid.uuid4().hex[:8]}"
    password = "Browser-UAT-strong-password-2026!"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            registration = context.request.post(
                f"{api_base}/api/auth/register",
                data={"email": email, "password": password, "workspace_name": workspace_name},
            )
            assert registration.status == 201, registration.text()
            registered = registration.json()
            assert registered["authenticated"] is True
            assert registered["user"]["workspace_role"] == "owner"

            me = context.request.get(f"{api_base}/api/auth/me")
            assert me.status == 200
            assert me.json()["user"]["email"] == email

            workspaces = context.request.get(f"{api_base}/api/workspaces")
            assert workspaces.status == 200
            workspace_data = workspaces.json()["data"]
            assert any(item["name"] == workspace_name for item in workspace_data)

            page = context.new_page()
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.get_by_role("heading", name="Growth command center.").wait_for(state="visible")
            page.locator("#overview").get_by_text(email, exact=True).wait_for(state="visible")

            # Exercise a real persisted, review-only content draft through the UI and API.
            page.get_by_label("Infographic title").fill("Browser UAT evidence-first infographic")
            page.get_by_label("Key points (3–6, one per line)").fill(
                "Compare products using the same criteria\n"
                "Verify claims against official source material\n"
                "Record limitations before publishing"
            )
            with page.expect_response(
                lambda response: response.url.endswith("/api/content/infographic")
                and response.request.method == "POST"
            ) as infographic_response_info:
                page.get_by_role("button", name="Create infographic SVG").click()
            infographic_response = infographic_response_info.value
            assert infographic_response.status == 201, infographic_response.text()
            infographic = infographic_response.json()
            assert infographic["requires_review"] is True
            assert infographic["publishing_started"] is False
            assert infographic["external_image_provider_used"] is False
            page.get_by_role("heading", name="Saved draft").wait_for(state="visible")
            page.get_by_text(f"Asset ID: {infographic['asset_id']}", exact=True).wait_for(state="visible")

            # Create an internal offer packet, explicitly not an affiliate-network listing.
            page.goto(f"{BASE_URL}/merchant/offers", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Merchant offers").wait_for(state="visible")
            offer_name = f"Browser UAT offer {uuid.uuid4().hex[:8]}"
            page.get_by_label("Offer / product name").fill(offer_name)
            page.get_by_label("Category").fill("Creator tools")
            page.get_by_label("Product description").fill(
                "A disposable integration-test offer packet used to verify workspace-scoped draft creation. "
                "It is not a real commercial offer and must not be listed externally."
            )
            page.get_by_label("Product URL").fill("https://example.com/browser-uat-product")
            page.get_by_label("Commission terms version/date").fill("terms-2026-10-28")
            page.get_by_label("Commission terms evidence URL").fill("https://example.com/browser-uat-terms")
            page.get_by_label("Seller authorization evidence URL").fill("https://example.com/browser-uat-authorization")
            page.get_by_label("Commission amount / rate").fill("25")
            page.get_by_label("Required affiliate disclosure").fill(
                "Affiliate disclosure: this disposable test packet is not a real commercial offer."
            )
            with page.expect_response(
                lambda response: response.url.endswith("/api/merchant/offers")
                and response.request.method == "POST"
            ) as offer_response_info:
                page.get_by_role("button", name="Save offer draft").click()
            offer_response = offer_response_info.value
            assert offer_response.status == 201, offer_response.text()
            offer = offer_response.json()
            assert offer["name"] == offer_name
            assert offer["status"] == "draft"
            assert offer["terms_verified"] is False
            assert offer["seller_authorization_verified"] is False
            assert offer["activation_allowed"] is False
            assert offer["affiliate_network_approval_status"] == "not_configured"
            assert offer["provider_submission_performed"] is False
            assert offer["marketplace_listed"] is False
            page.locator("main [role='status']").wait_for(state="visible")
            assert "External affiliate-network approval remains not_configured." in page.locator("main [role='status']").inner_text()
            page.get_by_text(offer_name, exact=True).wait_for(state="visible")
        finally:
            browser.close()
