from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import uuid

from backend.config import get_settings

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

            # Build a real public landing form using the authenticated workspace token.
            landing_response = context.request.post(
                f"{api_base}/api/landing/page",
                data={
                    "headline": "A practical affiliate starter guide",
                    "subheadline": "A consent-first resource for independent marketers.",
                    "benefit_bullets": ["Review claims against evidence", "Compare offers on consistent criteria"],
                    "privacy_url": "https://example.com/privacy",
                    "lead_magnet": "Browser UAT starter guide",
                    "audience": "affiliate marketers",
                },
                headers={"X-CSRF-Token": registered["csrf_token"]},
            )
            assert landing_response.status == 200, landing_response.text()
            landing_html = landing_response.text()
            token_match = re.search(r'name="workspace_token"\s+value="([^"]+)"', landing_html)
            assert token_match is not None, "generated landing form must contain a signed workspace token"
            workspace_token = token_match.group(1)

            # The public form must not submit without the required explicit-consent checkbox.
            public_posts: list[str] = []
            def block_public_capture(route):
                public_posts.append(route.request.url)
                route.fulfill(status=422, content_type="application/json", body='{"detail":"test submission should be blocked"}')
            page.route("http://127.0.0.1:8000/api/public/leads/capture", block_public_capture)
            page.route("https://cdn.tailwindcss.com", lambda route: route.fulfill(
                status=200, content_type="application/javascript", body=""
            ))
            browser_landing_html = landing_html.replace(
                "<head>", '<head><base href="http://127.0.0.1:8000/">', 1
            )
            page.set_content(browser_landing_html, wait_until="domcontentloaded")
            page.get_by_label("Email address").fill(f"no-consent-{uuid.uuid4().hex}@example.test")
            page.get_by_role("button", name="Send me the resource").click()
            assert page.locator('input[name="consent"]').evaluate("(element) => element.validity.valueMissing") is True
            assert public_posts == []

            # The server independently rejects missing consent, even when bypassing HTML validation.
            missing_consent = context.request.post(
                f"{api_base}/api/public/leads/capture",
                data={
                    "email": f"no-consent-api-{uuid.uuid4().hex}@example.test",
                    "consent": False,
                    "lead_magnet": "Browser UAT starter guide",
                    "audience": "affiliate marketers",
                    "offer": {},
                    "consent_source": "browser_uat",
                    "workspace_token": workspace_token,
                },
                headers={"Accept": "application/json"},
            )
            assert missing_consent.status == 422

            # Capture a real consented lead, then exercise the signed unsubscribe route.
            subscriber_email = f"subscriber-{uuid.uuid4().hex}@example.test"
            captured = context.request.post(
                f"{api_base}/api/public/leads/capture",
                data={
                    "email": subscriber_email,
                    "consent": True,
                    "lead_magnet": "Browser UAT starter guide",
                    "audience": "affiliate marketers",
                    "offer": {},
                    "consent_source": "browser_uat",
                    "workspace_token": workspace_token,
                    "resubscribe_confirmed": False,
                },
                headers={"Accept": "application/json"},
            )
            assert captured.status == 201, captured.text()
            captured_payload = captured.json()
            lead_id = captured_payload["lead_id"]
            assert captured_payload["workspace_id"] == registered["user"]["workspace_id"]

            timestamp = int(time.time())
            settings = get_settings()
            signing_secret = (settings.tracking_hmac_secret or settings.app_session_secret).encode()
            signature = hmac.new(
                signing_secret,
                f"unsubscribe:{lead_id}:{timestamp}".encode(),
                hashlib.sha256,
            ).hexdigest()
            unsubscribe = context.request.get(
                f"{api_base}/unsubscribe/{lead_id}?ts={timestamp}&sig={signature}"
            )
            assert unsubscribe.status == 200, unsubscribe.text()
            assert "You are unsubscribed" in unsubscribe.text()

            leads_after_unsubscribe = context.request.get(f"{api_base}/api/leads")
            assert leads_after_unsubscribe.status == 200, leads_after_unsubscribe.text()
            lead = next(item for item in leads_after_unsubscribe.json()["data"] if item["id"] == lead_id)
            assert lead["email"] == subscriber_email
            assert lead["unsubscribed"] is True

            # Consent alone must not silently reverse a previous unsubscribe decision.
            blocked_resubscribe = context.request.post(
                f"{api_base}/api/public/leads/capture",
                data={
                    "email": subscriber_email,
                    "consent": True,
                    "lead_magnet": "Browser UAT starter guide",
                    "audience": "affiliate marketers",
                    "offer": {},
                    "consent_source": "browser_uat",
                    "workspace_token": workspace_token,
                    "resubscribe_confirmed": False,
                },
                headers={"Accept": "application/json"},
            )
            assert blocked_resubscribe.status == 422
            assert "explicit resubscribe confirmation required" in blocked_resubscribe.json()["detail"]
            leads_still_suppressed = context.request.get(f"{api_base}/api/leads")
            assert leads_still_suppressed.status == 200
            still_unsubscribed = next(
                item for item in leads_still_suppressed.json()["data"] if item["id"] == lead_id
            )
            assert still_unsubscribed["unsubscribed"] is True
        finally:
            browser.close()



def test_persisted_landing_page_requires_owner_approval_and_supports_unpublish():
    api_base = "http://127.0.0.1:8000"
    email = f"landing-pages-{uuid.uuid4().hex}@example.test"
    workspace_name = f"Landing Workspace {uuid.uuid4().hex[:8]}"
    password = "Landing-UAT-strong-password-2026!"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            registration = context.request.post(
                api_base + "/api/auth/register",
                data={"email": email, "password": password, "workspace_name": workspace_name},
            )
            assert registration.status == 201, registration.text()
            registered = registration.json()
            csrf = registered["csrf_token"]

            page = context.new_page()
            page.goto(BASE_URL + "/landing-pages", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Landing pages and funnels").wait_for(state="visible")
            page.get_by_label("Headline", exact=True).fill("A clear creator guide")
            page.get_by_label("Subheadline").fill("A practical, evidence-first resource for independent creators.")
            page.get_by_label("Benefit bullets (one per line)").fill(
                "Choose products using consistent criteria\n"
                "Verify claims against official sources\n"
                "Keep limitations visible before deciding"
            )
            page.get_by_label("Privacy policy URL").fill("https://example.com/privacy")
            page.get_by_label("Lead magnet / resource").fill("Creator starter guide")
            page.get_by_label("Audience").fill("Independent creators")
            page.get_by_label("Affiliate disclosure").fill(
                "Disclosure: this resource may contain affiliate links and qualifying purchases may earn a commission."
            )
            with page.expect_response(
                lambda response: response.url.endswith("/api/landing/pages")
                and response.request.method == "POST"
            ) as create_info:
                page.get_by_role("button", name="Save landing page draft").click()
            created_response = create_info.value
            assert created_response.status == 201, created_response.text()
            created = created_response.json()
            asset_id = created["id"]
            assert created["status"] == "draft"
            assert created["public_url"] is None
            assert created["requires_review"] is True
            assert created["publishing_started"] is False
            assert context.request.get(api_base + "/p/" + asset_id).status == 404

            draft_card = page.locator('[data-testid="landing-page-' + asset_id + '"]')
            draft_card.get_by_role("heading", name="A clear creator guide").wait_for(state="visible")
            publish_button = draft_card.get_by_role("button", name="Publish page")
            assert publish_button.is_disabled()

            preview = context.request.get(api_base + created["preview_url"])
            assert preview.status == 200, preview.text()
            preview_html = preview.text()
            assert "cdn.tailwindcss.com" not in preview_html
            assert 'name="consent" value="yes" required' in preview_html
            assert 'name="workspace_token" value="' in preview_html
            assert "content-security-policy" in {header.lower() for header in preview.headers}
            assert "noindex" in preview.headers.get("x-robots-tag", "")

            other = browser.new_context()
            try:
                other_email = f"landing-other-{uuid.uuid4().hex}@example.test"
                other_registration = other.request.post(
                    api_base + "/api/auth/register",
                    data={
                        "email": other_email,
                        "password": "Other-Landing-UAT-password-2026!",
                        "workspace_name": "Other Landing Workspace",
                    },
                )
                assert other_registration.status == 201, other_registration.text()
                other_session = other_registration.json()
                assert other.request.get(api_base + created["preview_url"]).status == 404
                other_publish = other.request.post(
                    api_base + "/api/landing/pages/" + asset_id + "/publish",
                    data={"confirm_public_publish": True},
                    headers={"X-CSRF-Token": other_session["csrf_token"]},
                )
                assert other_publish.status == 404
            finally:
                other.close()

            denied = context.request.post(
                api_base + "/api/landing/pages/" + asset_id + "/publish",
                data={"confirm_public_publish": False},
                headers={"X-CSRF-Token": csrf},
            )
            assert denied.status == 409
            assert context.request.get(api_base + "/p/" + asset_id).status == 404

            draft_card.get_by_label("I reviewed this page and approve making it public.").check()
            with page.expect_response(
                lambda response: response.url.endswith("/api/landing/pages/" + asset_id + "/publish")
                and response.request.method == "POST"
            ) as publish_info:
                publish_button.click()
            published_response = publish_info.value
            assert published_response.status == 200, published_response.text()
            published = published_response.json()
            assert published["status"] == "published"
            assert published["public_url"] == api_base + "/p/" + asset_id
            assert published["publishing_started"] is True

            public_page = context.request.get(published["public_url"])
            assert public_page.status == 200, public_page.text()
            public_html = public_page.text()
            assert 'name="workspace_token" value="' in public_html
            assert 'name="consent" value="yes" required' in public_html
            assert "cdn.tailwindcss.com" not in public_html
            assert "content-security-policy" in public_page.headers
            refreshed = context.request.get(published["public_url"])
            assert refreshed.status == 200
            assert 'name="workspace_token" value="' in refreshed.text()

            utm_email = f"utm-capture-{uuid.uuid4().hex}@example.test"
            tracked_url = (
                published["public_url"]
                + "?utm_source=weekly%20newsletter&utm_medium=email"
                + "&utm_campaign=creator_launch&utm_content=guide%20%26%20checklist"
                + "&utm_term=solo_creator&utm_id=ignored"
            )
            tracked_page = context.new_page()
            tracked_response = tracked_page.goto(tracked_url, wait_until="domcontentloaded")
            assert tracked_response is not None and tracked_response.status == 200
            tracked_html = tracked_page.content()
            assert 'name="utm_source" value="weekly newsletter"' in tracked_html
            assert 'name="utm_medium" value="email"' in tracked_html
            assert 'name="utm_campaign" value="creator_launch"' in tracked_html
            assert 'name="utm_content" value="guide &amp; checklist"' in tracked_html
            assert 'name="utm_term" value="solo_creator"' in tracked_html
            assert 'name="utm_id"' not in tracked_html
            tracked_page.get_by_label("Email address").fill(utm_email)
            tracked_page.locator('input[name="consent"]').check()
            tracked_page.get_by_role("button", name="Send me the resource").click()
            tracked_page.get_by_role("heading", name="You're on the list").wait_for(state="visible")

            lead_response = context.request.get(api_base + "/api/leads")
            assert lead_response.status == 200, lead_response.text()
            tracked_lead = next(
                item for item in lead_response.json()["data"] if item["email"] == utm_email
            )
            expected_utm = {
                "utm_source": "weekly newsletter",
                "utm_medium": "email",
                "utm_campaign": "creator_launch",
                "utm_content": "guide & checklist",
                "utm_term": "solo_creator",
            }
            assert tracked_lead["attribution"]["first_touch"] == expected_utm
            assert tracked_lead["attribution"]["last_touch"] == expected_utm

            tracked_page.goto(BASE_URL + "/leads", wait_until="domcontentloaded")
            tracked_page.get_by_role("heading", name="Leads & attribution").wait_for(state="visible")
            lead_record = tracked_page.locator('[data-testid="lead-record-' + tracked_lead["id"] + '"]')
            lead_record.get_by_role("heading", name=utm_email).wait_for(state="visible")
            first_touch_card = lead_record.locator("section").nth(0)
            last_touch_card = lead_record.locator("section").nth(1)
            first_touch_card.get_by_text("weekly newsletter", exact=True).wait_for(state="visible")
            last_touch_card.get_by_text("weekly newsletter", exact=True).wait_for(state="visible")
            first_touch_card.get_by_text("guide & checklist", exact=True).wait_for(state="visible")
            last_touch_card.get_by_text("guide & checklist", exact=True).wait_for(state="visible")

            # A persisted draft is not public until owner/admin confirmation.
            published_card = page.locator('[data-testid="landing-page-' + asset_id + '"]')
            published_card.get_by_role("button", name="Unpublish page").wait_for(state="visible")
            with page.expect_response(
                lambda response: response.url.endswith("/api/landing/pages/" + asset_id + "/unpublish")
                and response.request.method == "POST"
            ) as unpublish_info:
                published_card.get_by_role("button", name="Unpublish page").click()
            unpublish_response = unpublish_info.value
            assert unpublish_response.status == 200, unpublish_response.text()
            assert unpublish_response.json()["status"] == "draft"
            assert context.request.get(published["public_url"]).status == 404
        finally:
            browser.close()



def test_distribution_queue_is_persisted_review_gated_and_never_claims_sent():
    api_base = "http://127.0.0.1:8000"
    email = f"distribution-queue-{uuid.uuid4().hex}@example.test"
    password = "Distribution-Queue-strong-password-2026!"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            registration = context.request.post(
                api_base + "/api/auth/register",
                data={"email": email, "password": password, "workspace_name": "Distribution Queue UAT"},
            )
            assert registration.status == 201, registration.text()
            asset_response = context.request.post(
                api_base + "/api/content/infographic",
                data={
                    "title": "A reviewed creator checklist",
                    "subtitle": "A practical distribution example",
                    "audience": "Independent creators",
                    "key_points": [
                        "Verify all product facts",
                        "Show affiliate disclosures clearly",
                        "Review audience and channel policies",
                    ],
                    "source_urls": ["https://example.invalid/creator-checklist"],
                },
            )
            assert asset_response.status == 201, asset_response.text()
            asset_id = asset_response.json()["asset_id"]

            page = context.new_page()
            page.goto(BASE_URL + "/distribution", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Distribution queue").wait_for(state="visible")
            page.get_by_label("Saved content asset").select_option(asset_id)
            page.get_by_label("Target channel").select_option("pinterest")
            with page.expect_response(
                lambda response: response.url.endswith("/api/distribution/queue") and response.request.method == "POST"
            ) as create_info:
                page.get_by_role("button", name="Add to review queue").click()
            created_response = create_info.value
            assert created_response.status == 201, created_response.text()
            item = created_response.json()
            assert item["status"] == "pending_review" and item["external_submission_status"] == "not_attempted"
            card = page.locator('[data-testid="distribution-queue-' + item["id"] + '"]')
            card.get_by_text("Pending review", exact=True).wait_for(state="visible")
            card.get_by_text("Not sent", exact=False).wait_for(state="visible")

            page.get_by_label("Target jurisdictions for review").fill("US, IN")
            card.get_by_label("I reviewed this content for the selected jurisdictions.").check()
            with page.expect_response(
                lambda response: response.url.endswith("/api/distribution/queue/" + item["id"] + "/approve")
                and response.request.method == "POST"
            ) as approve_info:
                card.get_by_role("button", name="Approve for dispatch review").click()
            approved_response = approve_info.value
            assert approved_response.status == 200, approved_response.text()
            approved = approved_response.json()
            assert approved["status"] == "approved_waiting_for_dispatch"
            assert approved["external_submission_status"] == "not_attempted" and approved["external_post_id"] is None
            card.get_by_text("Approved — not sent", exact=True).wait_for(state="visible")
            card.get_by_text("a separate dispatch confirmation and verified provider capability are required", exact=False).wait_for(state="visible")
        finally:
            browser.close()
