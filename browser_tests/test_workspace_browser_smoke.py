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
        finally:
            browser.close()
