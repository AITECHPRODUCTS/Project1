from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import uuid
from urllib.parse import parse_qs, urlparse

from backend.config import get_settings

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def _fulfill_json(route, payload: dict, status: int = 200) -> None:
    route.fulfill(status=status, content_type="application/json", headers={"access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-credentials": "true"}, body=json.dumps(payload))


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


def test_ad_guardrails_browser_surfaces_ambiguous_provider_snapshot_block():
    plan = {
        "id": "plan-ambiguous",
        "campaign_name": "Ambiguous snapshot test campaign",
        "daily_budget_usd": "40.00",
        "status": "draft",
        "platforms": ["meta"],
        "created_at": None,
    }
    guardrail = {
        "id": "guardrail-ambiguous",
        "campaign_plan_id": "plan-ambiguous",
        "daily_spend_cap_usd": "35.00",
        "campaign_spend_cap_usd": "500.00",
        "minimum_roas": "1.20",
        "maximum_cpa_usd": "35.00",
        "minimum_verified_impressions": 1000,
        "minimum_verified_clicks": 30,
        "minimum_verified_conversions": 3,
        "kill_switch_engaged": False,
        "stop_latched": False,
        "last_evaluated_at": "2026-10-29T06:00:00+00:00",
        "last_evaluation": {
            "status": "blocked_ambiguous_provider_snapshots",
            "snapshot_conflicts": [{
                "platform": "meta",
                "creative_id": "creative-1",
                "day": "2026-10-29",
                "observed_at": "2026-10-29T05:00:00+00:00",
                "conflicting_fields": ["commission_usd", "spend_usd"],
                "candidate_count": 2,
            }],
            "breaches": [],
            "provider_action_executed": False,
            "live_spend_authorized": False,
        },
        "live_spend_authorized": False,
        "external_campaign_changes_executed": False,
        "execution_note": "Review only.",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_ads(route):
                if "/api/ads/plans?" in route.request.url:
                    _fulfill_json(route, {"count": 1, "data": [plan]})
                elif "/api/ads/guardrails?" in route.request.url:
                    _fulfill_json(route, {"count": 1, "data": [guardrail]})
                else:
                    _fulfill_json(route, {"detail": "Unexpected API request"}, status=404)

            page.route("**/api/ads/**", handle_ads)
            page.goto(f"{BASE_URL}/ads/guardrails", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Ad budget guardrails").wait_for(state="visible")
            page.get_by_role("alert").get_by_text(
                "Conflicting provider snapshots — evaluation blocked"
            ).wait_for(state="visible")
            alert = page.locator("main [role='alert']")
            assert "creative-1" in alert.inner_text()
            assert "commission_usd, spend_usd" in alert.inner_text()
            assert "no remote campaign action was executed" in alert.inner_text().lower()
            assert alert.count() == 1
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





def test_affiliate_offer_catalog_searches_filters_sorts_and_paginates_without_claiming_verification():
    requests: list[dict[str, list[str]]] = []

    def offer_row(index: int) -> dict:
        provider_claimed = index == 0
        has_metrics = index != 1
        return {
            "id": "catalog-offer-" + str(index),
            "network": "clickbank",
            "external_id": "provider-" + str(index),
            "name": "Analytics offer " + str(index),
            "url": "https://merchant.example/offers/" + str(index),
            "category": "analytics",
            "description": "Example persisted offer entry for catalog UI acceptance.",
            "reward_type": "percentage",
            "reward_value": "20",
            "cookie_days": 30 if has_metrics else None,
            "traffic_score": 12.5 if has_metrics else None,
            "gravity_score": 3.0 if has_metrics else None,
            "normalized_gravity": 0.6 if has_metrics else None,
            "epc": 1.25 if has_metrics else None,
            "conversion_rate": 0.08 if has_metrics else None,
            "recurring_commission": True if has_metrics else None,
            "source_stars": 4.5 if has_metrics else None,
            "verified": provider_claimed,
            "verification_basis": "provider_claimed_unattested" if provider_claimed else "provider_not_verified_or_unknown",
            "source_url": "https://provider.example/programs/" + str(index),
            "updated_at": "2026-10-28T12:00:00+00:00",
        }

    def handle_catalog(route):
        path = urlparse(route.request.url).path
        if path == "/api/offers/shortlists" and route.request.method == "GET":
            _fulfill_json(route, {"count": 0, "limit": 100, "data": []})
            return
        query = parse_qs(urlparse(route.request.url).query)
        requests.append(query)
        offset = int(query.get("offset", ["0"])[0])
        if query.get("q") == ["analytics"]:
            rows = [offer_row(501)]
            total = 1
            offset = 0
        elif offset == 0:
            rows = [offer_row(index) for index in range(20)]
            total = 23
        else:
            rows = [offer_row(index) for index in range(20, 23)]
            total = 23
        _fulfill_json(route, {
            "count": len(rows),
            "total_count": total,
            "offset": offset,
            "limit": 20,
            "data": rows,
        })

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_non_admin(route):
                _fulfill_json(route, {
                    "authenticated": True,
                    "user": {
                        "email": "workspace-owner@example.invalid",
                        "is_admin": False,
                        "workspace_id": "browser-workspace",
                        "workspace_role": "owner",
                    },
                    "csrf_token": "browser-csrf-token",
                })

            page.route("**/api/auth/me", handle_non_admin)
            page.route("**/api/offers**", handle_catalog)
            page.route("**/api/integrations/openaffiliate/sync-status", lambda route: _fulfill_json(route, {
                "provider": "openaffiliate", "state": "never_synced", "last_attempt_at": None,
                "created": None, "updated": None, "registry_total": None, "requested_limit": None,
                "query_supplied": False, "error_type": None, "source_attestation_verified": False,
                "note": "This is an audit record, not independent source verification.",
            }))
            page.route("**/api/integrations/openaffiliate/sync-history**", lambda route: _fulfill_json(route, {
                "provider": "openaffiliate", "count": 0, "limit": 10,
                "source_attestation_verified": False,
                "note": "History contains only local audit outcomes.",
                "items": [],
            }))
            page.goto(f"{BASE_URL}/offers", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Affiliate offer catalog").wait_for(state="visible")
            page.get_by_text("Showing 1-20 of 23 results").wait_for(state="visible")
            page.get_by_text("Provider claimed — not independently attested").first.wait_for(state="visible")
            assert page.locator('[data-testid="offer-epc-catalog-offer-1"]').inner_text().endswith("Unknown")
            assert requests[0]["sort_by"] == ["epc"]
            assert requests[0]["sort_order"] == ["desc"]
            assert requests[0]["offset"] == ["0"]

            page.get_by_role("button", name="Next page").click()
            page.get_by_text("Showing 21-23 of 23 results").wait_for(state="visible")
            assert requests[-1]["offset"] == ["20"]

            page.get_by_label("Search terms").fill("analytics")
            page.get_by_label("Affiliate network").fill("clickbank")
            page.get_by_role("button", name="Search catalog").click()
            page.get_by_text("Showing 1-1 of 1 results").wait_for(state="visible")
            assert requests[-1]["q"] == ["analytics"]
            assert requests[-1]["network"] == ["clickbank"]
            assert requests[-1]["offset"] == ["0"]
            assert page.locator("main [role='alert']").count() == 0
            page.get_by_test_id("sync-admin-gate").wait_for(state="visible")
            assert page.get_by_test_id("sync-openaffiliate-catalog").count() == 0
        finally:
            browser.close()


def test_platform_admin_can_sync_persisted_openaffiliate_catalog_explicitly():
    calls: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_admin(route):
                _fulfill_json(route, {
                    "authenticated": True,
                    "user": {
                        "email": "platform-admin@example.invalid",
                        "is_admin": True,
                        "workspace_id": "platform-workspace",
                        "workspace_role": "owner",
                    },
                    "csrf_token": "browser-admin-csrf-token",
                })

            status_requests: list[str] = []
            history_requests: list[str] = []

            def handle_sync_history(route):
                history_requests.append(route.request.url)
                if calls:
                    _fulfill_json(route, {
                        "provider": "openaffiliate", "count": 2, "limit": 10,
                        "source_attestation_verified": False,
                        "note": "History contains local sync audit outcomes only.",
                        "items": [
                            {
                                "state": "completed", "attempted_at": "2026-10-28T17:00:00+00:00",
                                "created": 2, "updated": 1, "registry_total": 23,
                                "requested_limit": 100, "query_supplied": False,
                                "error_type": None, "source_attestation_verified": False,
                            },
                            {
                                "state": "failed", "attempted_at": "2026-10-28T16:55:00+00:00",
                                "created": None, "updated": None, "registry_total": None,
                                "requested_limit": 100, "query_supplied": True,
                                "error_type": "TimeoutError", "source_attestation_verified": False,
                            },
                        ],
                    })
                else:
                    _fulfill_json(route, {
                        "provider": "openaffiliate", "count": 0, "limit": 10,
                        "source_attestation_verified": False,
                        "note": "History contains local sync audit outcomes only.",
                        "items": [],
                    })

            def handle_sync_status(route):
                status_requests.append(route.request.url)
                if calls:
                    _fulfill_json(route, {
                        "provider": "openaffiliate", "state": "completed", "last_attempt_at": "2026-10-28T17:00:00+00:00",
                        "created": 2, "updated": 1, "registry_total": 23, "requested_limit": 100,
                        "query_supplied": False, "error_type": None, "source_attestation_verified": False,
                        "note": "This is an audited local sync outcome, not independent provider identity or source authenticity.",
                    })
                else:
                    _fulfill_json(route, {
                        "provider": "openaffiliate", "state": "never_synced", "last_attempt_at": None,
                        "created": None, "updated": None, "registry_total": None, "requested_limit": None,
                        "query_supplied": False, "error_type": None, "source_attestation_verified": False,
                        "note": "This is an audited local sync outcome, not independent provider identity or source authenticity.",
                    })

            def handle_offers(route):
                if route.request.method == "POST":
                    calls.append({
                        "method": route.request.method,
                        "url": route.request.url,
                        "csrf": route.request.headers.get("x-csrf-token", ""),
                    })
                    _fulfill_json(route, {
                        "created": 2,
                        "updated": 1,
                        "registry_total": 23,
                        "traffic_score_note": "Unknown unless upstream actually supplies the field.",
                    })
                    return
                _fulfill_json(route, {
                    "count": 1,
                    "total_count": 1,
                    "offset": 0,
                    "limit": 20,
                    "data": [{
                        "id": "synced-offer-1",
                        "network": "openaffiliate",
                        "external_id": "synced-offer-1",
                        "name": "Synced partner program",
                        "url": "https://merchant.example/offer",
                        "category": "software",
                        "description": "Directory entry returned by a successful sync fixture.",
                        "reward_type": "percentage",
                        "reward_value": "20",
                        "cookie_days": 30,
                        "traffic_score": None,
                        "gravity_score": None,
                        "normalized_gravity": None,
                        "epc": None,
                        "conversion_rate": None,
                        "recurring_commission": None,
                        "source_stars": None,
                        "verified": False,
                        "verification_basis": "provider_not_verified_or_unknown",
                        "source_url": "https://provider.example/programs/synced-offer-1",
                        "updated_at": None,
                    }],
                })

            page.route("**/api/auth/me", handle_admin)
            page.route("**/api/integrations/openaffiliate/sync-status", handle_sync_status)
            page.route("**/api/integrations/openaffiliate/sync-history**", handle_sync_history)
            page.route("**/api/offers**", handle_offers)
            page.goto(f"{BASE_URL}/offers", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Affiliate offer catalog").wait_for(state="visible")
            button = page.get_by_role("button", name="Sync OpenAffiliate catalog")
            button.wait_for(state="visible")
            button.click()
            page.get_by_test_id("openaffiliate-sync-result").wait_for(state="visible")
            result_text = page.get_by_test_id("openaffiliate-sync-result").inner_text()
            assert "2 created, 1 updated" in result_text
            assert "upstream registry total 23" in result_text
            assert "remain unverified" in result_text
            page.get_by_role("heading", name="Synced partner program").wait_for(state="visible")
            assert len(calls) == 1
            assert calls[0]["method"] == "POST"
            assert urlparse(calls[0]["url"]).path == "/api/offers/sync"
            assert parse_qs(urlparse(calls[0]["url"]).query) == {"limit": ["100"]}
            assert calls[0]["csrf"] == "browser-admin-csrf-token"
            page.get_by_text("Last sync completed successfully.").wait_for(state="visible")
            page.get_by_test_id("openaffiliate-sync-status").get_by_text("2 created · 1 updated · upstream registry total 23").wait_for(state="visible")
            page.get_by_test_id("sync-history-item-completed-0").wait_for(state="visible")
            page.get_by_test_id("sync-history-item-failed-1").wait_for(state="visible")
            page.get_by_text("Recorded error type: TimeoutError").wait_for(state="visible")
            assert len(status_requests) >= 2
            assert all(urlparse(url).path == "/api/integrations/openaffiliate/sync-status" for url in status_requests)
            assert len(history_requests) >= 2
            assert all(urlparse(url).path == "/api/integrations/openaffiliate/sync-history" for url in history_requests)
            assert page.locator("main [role='alert']").count() == 0
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
            unsubscribe_url = f"{api_base}/unsubscribe/{lead_id}?ts={timestamp}&sig={signature}"
            unsubscribe_confirmation = context.request.get(unsubscribe_url)
            assert unsubscribe_confirmation.status == 200, unsubscribe_confirmation.text()
            assert "Confirm unsubscribe" in unsubscribe_confirmation.text()
            assert 'method="post"' in unsubscribe_confirmation.text()
            assert "You are unsubscribed" not in unsubscribe_confirmation.text()

            # Link previews/scanners must not change recipient preferences; only
            # the explicit browser confirmation POST performs the opt-out.
            leads_after_link_preview = context.request.get(f"{api_base}/api/leads")
            assert leads_after_link_preview.status == 200, leads_after_link_preview.text()
            lead_before_confirmation = next(
                item for item in leads_after_link_preview.json()["data"] if item["id"] == lead_id
            )
            assert lead_before_confirmation["unsubscribed"] is False

            unsubscribe = context.request.post(
                unsubscribe_url,
                form={"confirm": "unsubscribe"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
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
            registered_session = registration.json()
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
                headers={"X-CSRF-Token": registered_session["csrf_token"]},
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



def test_commission_calculator_skill_studio_preset_loads_contract_and_fixture():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/skills/packages**", lambda route: _fulfill_json(route, {"count": 0, "data": []}))
            page.goto(f"{BASE_URL}/skills", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Governed skill packages").wait_for(state="visible")
            page.get_by_label("Safe runtime handler").select_option("research.commission_calculator")
            assert page.get_by_label("Skill ID").input_value() == "research/commission-calculator"
            assert page.get_by_label("Display name").input_value() == "Commission calculator"
            input_schema = json.loads(page.get_by_label("Input JSON schema").input_value())
            assert "monthly_visitors" in input_schema["properties"]
            assert "click_through_rate_pct" in input_schema["properties"]
            assert "programs" in input_schema["properties"]
            fixtures = json.loads(page.get_by_label("Contract fixtures JSON").input_value())
            assert len(fixtures) == 1
            assert fixtures[0]["expected_output"]["programs"][0]["estimated_12_month_commission"] == "120.000000"
            assert fixtures[0]["expected_output"]["earnings_guaranteed"] is False
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()



def test_commission_calculator_user_journey_submits_assumptions_and_shows_review_draft():
    response = {
        "asset_id": "projection-draft-001",
        "asset_status": "draft",
        "requires_review": True,
        "publishing_started": False,
        "programs": [{
            "name": "One-time Example",
            "reward_type": "cps_one_time",
            "currency": "USD",
            "commission_per_conversion_amount": "10.000000",
            "expected_monthly_clicks": "10.000000",
            "expected_monthly_conversions": "1.000000",
            "estimated_first_month_commission": "10.000000",
            "estimated_12_month_commission": "120.000000",
            "recurring_paid_months": None,
            "projection_basis": "one-time commission for each monthly conversion cohort",
        }],
        "measurement_basis": {
            "monthly_visitors": 100,
            "click_through_rate_pct_assumption": "10.000000",
            "affiliate_conversion_rate_pct_assumption": "10.000000",
        },
        "currency_comparison": "USD",
        "input_provenance": "caller_supplied_assumptions",
        "provider_metrics_verified": False,
        "earnings_guaranteed": False,
        "external_provider_calls_made": False,
        "money_transferred": False,
        "requires_human_review": True,
        "notes": [
            "Clicks, conversions and commissions are expected-value estimates, not observed counts or earnings.",
            "The projection assumes constant monthly visitors and rates, with no refunds, cancellations, fraud or attribution loss.",
            "Recurring projections assume each cohort continues paying for the supplied duration; churn is not modeled.",
            "No market benchmarks or provider metrics were fetched or inferred.",
        ],
    }
    submitted = {}

    def handle_calculation(route):
        submitted.update(route.request.post_data_json)
        _fulfill_json(route, response)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/research/commission-calculator", handle_calculation)
            page.goto(f"{BASE_URL}/commission-calculator", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Commission projection calculator").wait_for(state="visible")
            page.get_by_label("Monthly visitors").fill("100")
            page.get_by_label("Click-through rate (%)").fill("10")
            page.get_by_label("Affiliate conversion rate (%)").fill("10")
            page.get_by_label("Program 1 name").fill("One-time Example")
            page.get_by_role("button", name="Estimate commissions").click()
            page.get_by_role("status").get_by_text("Projection saved as a workspace draft").wait_for(state="visible")
            assert submitted["monthly_visitors"] == 100
            assert submitted["programs"][0]["commission_value"] == 20
            assert "average_order_value" in submitted["programs"][0]
            assert page.get_by_text("USD 120.000000").count() >= 1
            assert page.get_by_text("Provider metrics verified: false").count() == 1
        finally:
            browser.close()



def test_commission_calculator_shows_and_reloads_workspace_saved_projection_history():
    created_result = {
        "asset_id": "history-projection-001",
        "asset_status": "draft",
        "requires_review": True,
        "publishing_started": False,
        "programs": [{
            "name": "History Program",
            "reward_type": "cps_one_time",
            "currency": "USD",
            "commission_per_conversion_amount": "10.000000",
            "expected_monthly_clicks": "10.000000",
            "expected_monthly_conversions": "1.000000",
            "estimated_first_month_commission": "10.000000",
            "estimated_12_month_commission": "120.000000",
            "recurring_paid_months": None,
            "projection_basis": "one-time commission for each monthly conversion cohort",
        }],
        "measurement_basis": {
            "monthly_visitors": 100,
            "click_through_rate_pct_assumption": "10.000000",
            "affiliate_conversion_rate_pct_assumption": "10.000000",
        },
        "currency_comparison": "USD",
        "input_provenance": "caller_supplied_assumptions",
        "provider_metrics_verified": False,
        "earnings_guaranteed": False,
        "external_provider_calls_made": False,
        "money_transferred": False,
        "requires_human_review": True,
        "notes": [
            "Clicks, conversions and commissions are expected-value estimates, not observed counts or earnings.",
            "The projection assumes constant monthly visitors and rates, with no refunds, cancellations, fraud or attribution loss.",
            "Recurring projections assume each cohort continues paying for the supplied duration; churn is not modeled.",
            "No market benchmarks or provider metrics were fetched or inferred.",
        ],
    }
    history_reads = {"count": 0}

    def handle_history(route):
        history_reads["count"] += 1
        if history_reads["count"] == 1:
            _fulfill_json(route, {"count": 0, "limit": 20, "offset": 0, "items": []})
        else:
            _fulfill_json(route, {
                "count": 1, "limit": 20, "offset": 0,
                "items": [{
                    "asset_id": "history-projection-001",
                    "title": "Commission projection — 1 program(s) — USD",
                    "asset_status": "draft",
                    "created_at": "2026-10-29T03:00:00+00:00",
                    "requires_review": True,
                    "publishing_started": False,
                    "assumptions": {},
                    "result": created_result,
                }],
            })

    def handle_calculation(route):
        _fulfill_json(route, created_result)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/research/commission-projections**", handle_history)
            page.route("**/api/research/commission-calculator", handle_calculation)
            page.goto(f"{BASE_URL}/commission-calculator", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Commission projection calculator").wait_for(state="visible")
            page.get_by_role("heading", name="Saved commission projections").wait_for(state="visible")
            page.get_by_text("No saved commission projections in this workspace yet.").wait_for(state="visible")

            page.get_by_label("Monthly visitors").fill("100")
            page.get_by_label("Click-through rate (%)").fill("10")
            page.get_by_label("Affiliate conversion rate (%)").fill("10")
            page.get_by_label("Program 1 name").fill("History Program")
            page.get_by_role("button", name="Estimate commissions").click()
            page.get_by_role("status").get_by_text("Projection saved as a workspace draft").wait_for(state="visible")
            page.get_by_text("history-projection-001", exact=True).wait_for(state="visible")
            assert history_reads["count"] >= 2
            page.get_by_role("button", name="View saved results").click()
            assert page.get_by_text("Loaded saved projection. It remains a draft requiring review.").count() == 1
            assert page.get_by_text("USD 120.000000").count() >= 1
        finally:
            browser.close()


def test_offer_shortlist_ui_creates_saves_compares_and_removes_persisted_catalog_items():
    import json

    lists: list[dict] = []
    saved: list[dict] = []
    offer = {
        "id": "offer-shortlist-1", "network": "openaffiliate", "external_id": "creator-suite",
        "name": "Creator Suite", "url": "https://merchant.example/creator-suite", "category": "creator",
        "description": "Email and analytics tools", "reward_type": "recurring_percentage", "reward_value": "20",
        "cookie_days": 45, "traffic_score": None, "gravity_score": None, "normalized_gravity": None,
        "epc": None, "conversion_rate": None, "recurring_commission": True, "source_stars": None,
        "verified": False, "verification_basis": "provider_not_verified_or_unknown",
        "source_url": None, "updated_at": None,
    }

    def summary(item):
        return {"id": item["id"], "name": item["name"], "description": "", "item_count": len(saved),
                "created_at": None, "updated_at": None}

    def detail():
        return {"id": "shortlist-1", "name": "Creator research", "description": "", "count": len(saved),
                "items": [{"item_id": "saved-item-1", "note": item["note"], "added_at": None, "offer": offer} for item in saved]}

    def handle_api(route):
        path = urlparse(route.request.url).path
        method = route.request.method
        if path == "/api/auth/me":
            _fulfill_json(route, {"authenticated": True, "user": {"email": "owner@example.invalid", "is_admin": False,
                "workspace_id": "browser-workspace", "workspace_role": "owner"}, "csrf_token": "browser-csrf-token"})
            return
        if path == "/api/offers/shortlists":
            if method == "GET":
                _fulfill_json(route, {"count": len(lists), "limit": 100, "data": [summary(item) for item in lists]})
            elif method == "POST":
                body = json.loads(route.request.post_data or "{}")
                item = {"id": "shortlist-1", "name": body["name"]}
                lists[:] = [item]
                _fulfill_json(route, {**summary(item), "item_count": 0}, status=201)
            else:
                _fulfill_json(route, {"detail": "unsupported"}, status=405)
            return
        if path == "/api/offers/shortlists/shortlist-1":
            if method == "GET":
                _fulfill_json(route, detail())
            elif method == "DELETE":
                lists.clear(); saved.clear()
                _fulfill_json(route, {"deleted": True, "id": "shortlist-1"})
            else:
                _fulfill_json(route, {"detail": "unsupported"}, status=405)
            return
        if path == "/api/offers/shortlists/shortlist-1/items":
            if method == "POST":
                submitted = json.loads(route.request.post_data or "{}")
                saved.append({"offer_id": offer["id"], "note": submitted.get("note", "")})
                _fulfill_json(route, {"id": "saved-item-1", "shortlist_id": "shortlist-1", "offer_id": offer["id"], "note": submitted.get("note", "")}, status=201)
            else:
                _fulfill_json(route, {"detail": "unsupported"}, status=405)
            return
        if path == "/api/offers/shortlists/shortlist-1/items/offer-shortlist-1" and method == "DELETE":
            saved.clear()
            _fulfill_json(route, {"deleted": True, "shortlist_id": "shortlist-1", "offer_id": offer["id"]})
            return
        if path == "/api/offers" or path.startswith("/api/offers?"):
            _fulfill_json(route, {"count": 1, "total_count": 1, "offset": 0, "limit": 20, "data": [offer]})
            return
        _fulfill_json(route, {"detail": "unexpected request"}, status=404)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/**", handle_api)
            page.goto(f"{BASE_URL}/offers", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Affiliate offer catalog").wait_for(state="visible")
            page.get_by_label("Create a saved list").fill("Creator research")
            page.get_by_role("button", name="Create list").click()
            page.get_by_test_id("shortlist-message").filter(has_text="Saved offer list created").wait_for(state="visible")
            page.get_by_label("Choose list to manage").select_option("shortlist-1")
            page.get_by_label("Review note for Creator Suite").fill("Confirm program terms before selection.")
            page.get_by_role("button", name="Save to selected list").click()
            page.get_by_test_id("selected-shortlist-items").get_by_text("Creator Suite").wait_for(state="visible")
            page.get_by_test_id("selected-shortlist-items").get_by_text("Confirm program terms before selection.").wait_for(state="visible")
            assert "EPC Unknown" in page.get_by_test_id("selected-shortlist-items").inner_text()
            page.get_by_role("button", name="Remove").click()
            page.get_by_text("This list is empty.", exact=False).wait_for(state="visible")
            page.get_by_role("button", name="Delete list").click()
            page.get_by_text("No saved lists yet.", exact=False).wait_for(state="visible")
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()


def test_offer_qualification_ui_records_review_only_decision_with_evidence():
    posted: list[dict] = []
    offer = {"id": "qualify-ui-1", "network": "openaffiliate", "external_id": "qualify-ui-1",
        "name": "Qualification UI candidate", "category": "software", "description": "Review terms before use.",
        "url": "https://merchant.example/terms", "cookie_days": None, "reward_type": None, "reward_value": None,
        "epc": None, "conversion_rate": None, "verification_basis": "provider_not_verified_or_unknown"}
    review = {"status": "not_reviewed", "account_eligibility": "unknown", "geography_fit": "unknown",
        "traffic_source_fit": "unknown", "terms_review": "unknown", "landing_page_review": "unknown",
        "disclosure_review": "unknown", "evidence_urls": [], "notes": "", "policy_version": "manual-review-v1",
        "reviewed_by": None, "reviewed_at": None, "evidence_basis": "operator_supplied_unverified",
        "affiliate_network_approval_implied": False}
    def handle_api(route):
        path = urlparse(route.request.url).path
        if path == "/api/auth/me":
            _fulfill_json(route, {"authenticated": True, "user": {"email": "reviewer@example.invalid", "is_admin": False,
                "workspace_id": "browser-workspace", "workspace_role": "owner"}, "csrf_token": "browser-csrf-token"})
        elif path == "/api/offers/qualification-queue":
            data = [] if review["status"] == "qualified" else [{"offer": offer, "qualification": review}]
            _fulfill_json(route, {"count": len(data), "total_count": len(data), "offset": 0, "limit": 50,
                "status_filter": "needs_review", "data": data, "note": "Operator-supplied unverified evidence."})
        elif path == "/api/offers/qualify-ui-1/qualification" and route.request.method == "POST":
            payload = json.loads(route.request.post_data or "{}"); posted.append(payload)
            if payload.get("status") == "qualified" and (not payload.get("evidence_urls") or any(payload.get(key) != "pass" for key in [
                "account_eligibility", "geography_fit", "traffic_source_fit", "terms_review", "landing_page_review", "disclosure_review"
            ])):
                _fulfill_json(route, {"detail": "qualified status requires complete evidence"}, status=422); return
            review.update(payload); review.update({"reviewed_by": "reviewer@example.invalid", "reviewed_at": "2026-10-29T00:00:00+00:00",
                "evidence_basis": "operator_supplied_unverified", "affiliate_network_approval_implied": False})
            _fulfill_json(route, {"offer_id": offer["id"], "status": review["status"], "activation_allowed": False,
                "evidence_basis": review["evidence_basis"], "affiliate_network_approval_implied": False})
        else:
            _fulfill_json(route, {"detail": "unexpected request"}, status=404)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(); page.route("**/api/**", handle_api)
            page.goto(f"{BASE_URL}/offers/qualification", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Offer qualification review").wait_for(state="visible")
            page.get_by_label("Decision").select_option("qualified")
            for label in ["Publisher account eligibility", "Target geography allowed", "Traffic sources allowed",
                          "Program terms reviewed", "Destination / landing page reviewed", "Affiliate disclosure ready"]:
                page.get_by_label(label).select_option("pass")
            page.get_by_label("Evidence URLs (one HTTPS URL per line)").fill("https://merchant.example/affiliate-terms")
            page.get_by_label("Reviewer notes").fill("Terms and traffic policy reviewed; provider approval remains unknown.")
            page.get_by_role("button", name="Save qualification review").click()
            page.get_by_test_id("qualification-message").wait_for(state="visible")
            assert "not network approval" in page.get_by_test_id("qualification-message").inner_text().lower()
            assert len(posted) == 1 and posted[0]["status"] == "qualified"
            assert posted[0]["evidence_urls"] == ["https://merchant.example/affiliate-terms"]
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()



def test_offer_qualification_queue_paginates_and_preserves_filter():
    responses: list[dict[str, list[str]]] = []

    def handle_queue(route):
        query = parse_qs(urlparse(route.request.url).query)
        responses.append(query)
        offset = int(query.get("offset", ["0"])[0])
        rows = []
        for index in range(offset, min(offset + 50, 52)):
            rows.append({
                "offer": {"id": f"offer-{index}", "network": "openaffiliate", "external_id": f"external-{index}",
                    "name": f"Offer {index}", "category": "software", "description": "Persisted catalog offer",
                    "url": "https://merchant.example/offer", "cookie_days": None, "reward_type": None,
                    "reward_value": None, "epc": None, "conversion_rate": None,
                    "verification_basis": "provider_not_verified_or_unknown"},
                "qualification": {"status": "not_reviewed", "account_eligibility": "unknown", "geography_fit": "unknown",
                    "traffic_source_fit": "unknown", "terms_review": "unknown", "landing_page_review": "unknown",
                    "disclosure_review": "unknown", "evidence_urls": [], "notes": "", "policy_version": "manual-review-v1",
                    "reviewed_by": None, "reviewed_at": None, "evidence_basis": "operator_supplied_unverified",
                    "affiliate_network_approval_implied": False},
            })
        _fulfill_json(route, {"count": len(rows), "total_count": 52, "offset": offset, "limit": 50,
            "status_filter": query.get("status", ["needs_review"])[0], "data": rows,
            "note": "Operator review does not imply provider approval."})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/auth/me", lambda route: _fulfill_json(route, {
                "authenticated": True, "user": {"email": "reviewer@example.invalid", "is_admin": False,
                    "workspace_id": "browser-workspace", "workspace_role": "owner"}, "csrf_token": "browser-csrf-token"}))
            page.route("**/api/offers/qualification-queue**", handle_queue)
            page.goto(f"{BASE_URL}/offers/qualification", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Offer qualification review").wait_for(state="visible")
            page.get_by_text("Showing 1–50 of 52 offers").wait_for(state="visible")
            assert page.get_by_role("button", name="Previous page").is_disabled()
            page.get_by_role("button", name="Next page").click()
            page.get_by_text("Showing 51–52 of 52 offers").wait_for(state="visible")
            assert responses[-1]["offset"] == ["50"]
            assert responses[-1]["status"] == ["needs_review"]
            assert page.get_by_role("button", name="Next page").is_disabled()
            page.get_by_role("button", name="Previous page").click()
            page.get_by_text("Showing 1–50 of 52 offers").wait_for(state="visible")
            assert responses[-1]["offset"] == ["0"]
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()



def test_offer_qualification_returns_to_valid_page_when_last_filtered_item_is_removed():
    qualified_ids: set[str] = set()
    queue_offsets: list[int] = []
    offers = [
        {"id": "alpha", "network": "openaffiliate", "external_id": "alpha", "name": "Alpha offer",
         "category": "software", "description": "First reviewable offer", "url": "https://merchant.example/alpha",
         "cookie_days": None, "reward_type": None, "reward_value": None, "epc": None, "conversion_rate": None,
         "verification_basis": "provider_not_verified_or_unknown"},
        {"id": "beta", "network": "openaffiliate", "external_id": "beta", "name": "Beta offer",
         "category": "software", "description": "Second reviewable offer", "url": "https://merchant.example/beta",
         "cookie_days": None, "reward_type": None, "reward_value": None, "epc": None, "conversion_rate": None,
         "verification_basis": "provider_not_verified_or_unknown"},
    ]

    def handle_api(route):
        path = urlparse(route.request.url).path
        if path == "/api/auth/me":
            _fulfill_json(route, {"authenticated": True, "user": {"email": "reviewer@example.invalid", "is_admin": False,
                "workspace_id": "browser-workspace", "workspace_role": "owner"}, "csrf_token": "browser-csrf-token"})
        elif path == "/api/offers/qualification-queue":
            query = parse_qs(urlparse(route.request.url).query)
            offset = int(query.get("offset", ["0"])[0])
            queue_offsets.append(offset)
            remaining = [offer for offer in offers if offer["id"] not in qualified_ids]
            rows = [{"offer": offer, "qualification": {
                "status": "not_reviewed", "account_eligibility": "unknown", "geography_fit": "unknown",
                "traffic_source_fit": "unknown", "terms_review": "unknown", "landing_page_review": "unknown",
                "disclosure_review": "unknown", "evidence_urls": [], "notes": "", "policy_version": "manual-review-v1",
                "reviewed_by": None, "reviewed_at": None, "evidence_basis": "operator_supplied_unverified",
                "affiliate_network_approval_implied": False}} for offer in remaining]
            _fulfill_json(route, {"count": len(rows[offset:offset + 1]), "total_count": len(rows), "offset": offset,
                "limit": 1, "status_filter": query.get("status", ["needs_review"])[0], "data": rows[offset:offset + 1],
                "note": "Operator review does not imply provider approval."})
        elif path.startswith("/api/offers/") and path.endswith("/qualification") and route.request.method == "POST":
            offer_id = path.split("/")[-2]
            payload = json.loads(route.request.post_data or "{}")
            if payload.get("status") == "qualified":
                qualified_ids.add(offer_id)
            _fulfill_json(route, {"offer_id": offer_id, "status": payload.get("status"), "activation_allowed": False,
                "evidence_basis": "operator_supplied_unverified", "affiliate_network_approval_implied": False})
        else:
            _fulfill_json(route, {"detail": "unexpected request"}, status=404)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/**", handle_api)
            page.goto(f"{BASE_URL}/offers/qualification", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Offer qualification review").wait_for(state="visible")
            page.get_by_role("button", name="Next page").click()
            page.get_by_text("Showing 2–2 of 2 offers").wait_for(state="visible")
            card = page.get_by_test_id("qualification-card")
            card.get_by_role("combobox", name="Decision").select_option("qualified")
            for label in ["Publisher account eligibility", "Target geography allowed", "Traffic sources allowed",
                          "Program terms reviewed", "Destination / landing page reviewed", "Affiliate disclosure ready"]:
                card.get_by_label(label).select_option("pass")
            card.get_by_label("Evidence URLs (one HTTPS URL per line)").fill("https://merchant.example/affiliate-terms")
            card.get_by_role("button", name="Save qualification review").click()
            # With only one matching item left, pagination controls are hidden;
            # assert the recovered page content instead of a pagination-only label.
            page.get_by_role("heading", name="Alpha offer").wait_for(state="visible")
            assert page.get_by_role("heading", name="Beta offer").count() == 0
            assert queue_offsets[-2:] == [1, 0]
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()


def test_leads_page_displays_email_confirmation_and_read_only_consent_history():
    lead = {
        "id": "lead-confirmed",
        "email": "reader@example.test",
        "lead_magnet": "Creator guide",
        "consented_at": "2026-10-28T10:00:00+00:00",
        "email_consent_confirmed_at": "2026-10-28T10:01:00+00:00",
        "consent_source": "persisted_landing_page",
        "unsubscribed": False,
        "purchased": False,
        "attribution": {"first_touch": {"utm_source": "newsletter"}, "last_touch": {}, "last_touch_at": None},
    }
    history = {
        "lead_id": "lead-confirmed",
        "count": 1,
        "read_only": True,
        "data": [{
            "id": "consent-event-1",
            "event_type": "consent_granted",
            "purpose": "email_marketing",
            "consent_text": "I agree to receive email updates about relevant offers and can unsubscribe at any time.",
            "policy_version": "email-marketing-v1",
            "source": "persisted_landing_page",
            "channel": "email",
            "metadata": {"explicit_checkbox_consent": True},
            "observed_at": "2026-10-28T10:00:00+00:00",
            "created_at": "2026-10-28T10:00:00+00:00",
        }],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_leads(route):
                if "/api/leads/lead-confirmed/consent-events" in route.request.url:
                    _fulfill_json(route, history)
                elif route.request.url.split("?", 1)[0].rstrip("/").endswith("/api/leads"):
                    _fulfill_json(route, {"count": 1, "total_count": 1, "limit": 50, "offset": 0, "data": [lead]})
                else:
                    _fulfill_json(route, {"detail": "Unexpected leads API request"}, status=404)

            page.route("**/api/leads**", handle_leads)
            page.goto(f"{BASE_URL}/leads", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Leads & attribution").wait_for(state="visible")
            page.get_by_text("Email confirmation: Confirmed", exact=False).wait_for(state="visible")
            page.get_by_text("Consent source: persisted_landing_page").wait_for(state="visible")
            page.get_by_role("button", name="View consent history").click()
            history_panel = page.get_by_role("region", name="Consent history for reader@example.test")
            history_panel.get_by_text("consent granted", exact=False).wait_for(state="visible")
            history_panel.get_by_text("email-marketing-v1").wait_for(state="visible")
            history_panel.get_by_text("I agree to receive email updates about relevant offers and can unsubscribe at any time.").wait_for(state="visible")
            assert history_panel.get_by_text("Read-only consent event ledger", exact=False).is_visible()
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()


def test_leads_page_paginates_and_recovers_when_last_page_becomes_stale():
    observed = "2026-10-28T10:00:00+00:00"
    first_page = [{
        "id": f"lead-{index}",
        "email": f"lead-{index}@example.test",
        "lead_magnet": "Creator guide",
        "consented_at": observed,
        "email_consent_confirmed_at": None,
        "consent_source": "persisted_landing_page",
        "unsubscribed": False,
        "purchased": False,
        "attribution": {"first_touch": {}, "last_touch": {}, "last_touch_at": None},
    } for index in range(50)]
    last_lead = {
        "id": "lead-50",
        "email": "lead-50@example.test",
        "lead_magnet": "Creator guide",
        "consented_at": observed,
        "email_consent_confirmed_at": observed,
        "consent_source": "persisted_landing_page",
        "unsubscribed": False,
        "purchased": False,
        "attribution": {"first_touch": {}, "last_touch": {}, "last_touch_at": None},
    }
    offset_zero_calls = [0]
    offset_fifty_calls = [0]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_leads(route):
                url = route.request.url
                if "/api/leads/" in url and "/consent-events" in url:
                    _fulfill_json(route, {"lead_id": "lead-50", "count": 0, "read_only": True, "data": []})
                elif "offset=50" in url:
                    offset_fifty_calls[0] += 1
                    if offset_fifty_calls[0] == 1:
                        _fulfill_json(route, {"count": 1, "total_count": 51, "limit": 50, "offset": 50, "data": [last_lead]})
                    else:
                        # Simulate the only record on page two being removed after it was viewed.
                        _fulfill_json(route, {"count": 0, "total_count": 50, "limit": 50, "offset": 50, "data": []})
                elif "offset=0" in url:
                    offset_zero_calls[0] += 1
                    total = 51 if offset_zero_calls[0] == 1 else 50
                    _fulfill_json(route, {"count": 50, "total_count": total, "limit": 50, "offset": 0, "data": first_page})
                else:
                    _fulfill_json(route, {"detail": "Unexpected leads API request"}, status=404)

            page.route("**/api/leads**", handle_leads)
            page.goto(f"{BASE_URL}/leads", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Leads & attribution").wait_for(state="visible")
            page.get_by_text("lead-0@example.test").wait_for(state="visible")
            page.get_by_role("button", name="Next").click()
            page.get_by_text("lead-50@example.test").wait_for(state="visible")
            page.get_by_text("page 2 of 2", exact=False).wait_for(state="visible")
            page.get_by_role("button", name="Refresh").click()
            page.get_by_text("lead-0@example.test").wait_for(state="visible")
            assert offset_fifty_calls[0] == 2
            assert offset_zero_calls[0] == 2
            assert page.get_by_role("button", name="Next").count() == 0
        finally:
            browser.close()


def test_leads_page_searches_email_and_resource_across_workspace_results():
    alpha = {
        "id": "lead-alpha",
        "email": "alpha@example.test",
        "lead_magnet": "Alpha guide",
        "consented_at": "2026-10-28T10:00:00+00:00",
        "email_consent_confirmed_at": None,
        "consent_source": "persisted_landing_page",
        "unsubscribed": False,
        "purchased": False,
        "attribution": {"first_touch": {}, "last_touch": {}, "last_touch_at": None},
    }
    beta = {
        **alpha,
        "id": "lead-beta",
        "email": "beta@example.test",
        "lead_magnet": "Beta handbook",
        "attribution": {"first_touch": {"utm_source": "partner-newsletter"}, "last_touch": {}, "last_touch_at": None},
    }
    requested_searches = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_leads(route):
                url = route.request.url
                if "/api/leads/" in url and "/consent-events" in url:
                    _fulfill_json(route, {"lead_id": "lead-beta", "count": 0, "read_only": True, "data": []})
                    return
                search_value = ""
                if "search=" in url:
                    search_value = url.split("search=", 1)[1].split("&", 1)[0]
                requested_searches.append(search_value)
                if search_value.lower() == "partner-newsletter":
                    _fulfill_json(route, {"count": 1, "total_count": 1, "limit": 50, "offset": 0, "data": [beta]})
                else:
                    _fulfill_json(route, {"count": 2, "total_count": 2, "limit": 50, "offset": 0, "data": [alpha, beta]})

            page.route("**/api/leads**", handle_leads)
            page.goto(f"{BASE_URL}/leads", wait_until="domcontentloaded")
            page.get_by_text("alpha@example.test").wait_for(state="visible")
            page.get_by_text("beta@example.test").wait_for(state="visible")
            page.get_by_label("Search all leads by email, resource or UTM").fill("partner-newsletter")
            page.get_by_role("button", name="Search", exact=True).click()
            page.get_by_text("beta@example.test").wait_for(state="visible")
            page.get_by_text("alpha@example.test").wait_for(state="hidden")
            assert requested_searches[-1] == "partner-newsletter"
            page.get_by_label("Filter UTM values on this page").fill("missing-utm")
            page.get_by_text("No matching leads").wait_for(state="visible")
            assert page.get_by_text("beta@example.test").count() == 0
        finally:
            browser.close()
