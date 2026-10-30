from __future__ import annotations

import json
import os
from urllib.parse import urlparse

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


def test_program_application_splits_multiple_evidence_urls_before_saving():
    submitted_packets: list[dict] = []
    evidence_urls = [
        "https://network.example.com/affiliate-terms",
        "https://network.example.com/publisher-policy",
    ]

    application_result = {
        "id": "packet-browser-test",
        "provider": "Example Affiliate Network",
        "program_name": "Example Publisher Program",
        "status": "draft",
        "readiness": {
            "ready_for_human_review": False,
            "blockers": ["official_program_terms_evidence_required"],
        },
        "provider_submission_status": "not_configured",
        "provider_submission_performed": False,
        "manual_handoff_only": True,
        "provider_approved": False,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                request = route.request
                path = urlparse(request.url).path

                if path == "/api/auth/me":
                    _fulfill_json(
                        route,
                        {
                            "authenticated": True,
                            "user": {
                                "user_id": "browser-user",
                                "email": "publisher@example.test",
                                "is_admin": False,
                                "workspace_id": "browser-workspace",
                                "workspace_role": "owner",
                            },
                            "csrf_token": "browser-csrf-token",
                        },
                    )
                    return

                if path == "/api/workspaces":
                    _fulfill_json(
                        route,
                        {
                            "active_workspace_id": "browser-workspace",
                            "data": [
                                {
                                    "id": "browser-workspace",
                                    "name": "Browser Test Workspace",
                                    "role": "owner",
                                    "is_active": True,
                                    "lifecycle_state": "active",
                                }
                            ],
                        },
                    )
                    return

                if path == "/api/status":
                    _fulfill_json(
                        route,
                        {
                            "app_name": "OmniAffiliateOS",
                            "environment": "test",
                            "execution_mode": "SEMI_AUTONOMOUS",
                            "knowledge_index_available": False,
                            "api_model_configured": False,
                            "email_delivery_configured": False,
                            "video_rendering_available": False,
                            "publishing_dry_run": True,
                            "ad_automation_execute": False,
                            "clicks": 0,
                            "conversion_events": 0,
                            "commission_recorded": 0,
                        },
                    )
                    return

                if path == "/api/resource-budget":
                    _fulfill_json(
                        route,
                        {
                            "daily_budget_usd": 10,
                            "daily_estimated_used_usd": 0,
                            "daily_estimated_remaining_usd": 10,
                            "niche_budget_usd": 10,
                            "note": "Browser-test budget fixture",
                        },
                    )
                    return

                if path == "/api/integrations":
                    _fulfill_json(
                        route,
                        {
                            "total": 0,
                            "counts": {"enabled": 0, "configured": 0},
                            "items": [],
                            "verification_policy": "Browser-test fixture only",
                        },
                    )
                    return

                if path == "/api/capabilities":
                    _fulfill_json(
                        route,
                        {
                            "statuses": [],
                            "counts": {},
                            "items": [],
                            "provider_items": [],
                            "global_policy": "Browser-test fixture only",
                        },
                    )
                    return

                if path == "/api/research/program-applications" and request.method == "POST":
                    submitted_packets.append(json.loads(request.post_data or "{}"))
                    _fulfill_json(route, application_result, status=201)
                    return

                if path.startswith("/api/"):
                    _fulfill_json(route, {"detail": "Unexpected API request"}, status=404)
                    return

                route.continue_()

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Growth command center.").wait_for(state="visible")

            page.locator("#program-applications").scroll_into_view_if_needed()
            page.locator("#program-app-provider").fill("Example Affiliate Network")
            page.locator("#program-app-name").fill("Example Publisher Program")
            page.locator("#program-app-url").fill("https://network.example.com/affiliate-terms")
            page.locator("#program-app-website").fill("https://publisher.example.test")
            page.locator("#program-app-audience").fill(
                "Readers seeking carefully sourced software education and product comparisons."
            )
            page.locator("#program-app-plan").fill(
                "We will publish evidence-based educational articles and clearly labeled product "
                "comparisons. Affiliate relationships will be disclosed, paid traffic will only "
                "be used where the program terms allow it, and unsupported product claims will "
                "not be published."
            )
            page.locator("#program-app-evidence").fill("\n".join(evidence_urls))

            with page.expect_response(
                lambda response: (
                    urlparse(response.url).path == "/api/research/program-applications"
                    and response.request.method == "POST"
                )
            ) as response_info:
                page.locator("#program-applications button[type='submit']").click()

            response = response_info.value
            assert response.status == 201, response.text()
            page.get_by_text("Provider submission: not_configured", exact=False).wait_for(
                state="visible"
            )

            assert len(submitted_packets) == 1
            assert submitted_packets[0]["evidence_urls"] == evidence_urls
            assert submitted_packets[0]["provider"] == "Example Affiliate Network"
            assert submitted_packets[0]["program_name"] == "Example Publisher Program"
            assert application_result["provider_submission_performed"] is False
            assert application_result["provider_approved"] is False
        finally:
            browser.close()

def test_webinar_agenda_splits_multiple_items_before_saving():
    submitted_events: list[dict] = []
    expected_agenda = ["Opening and objectives", "Product demonstration and questions"]
    event_result = {
        "id": "webinar-browser-test",
        "public_id": "public-webinar-browser-test",
        "title": "Browser regression webinar",
        "status": "draft",
        "public_path": "/webinar/public-webinar-browser-test",
        "start_at": "2099-01-01T10:00:00+05:30",
        "end_at": "2099-01-01T11:00:00+05:30",
        "timezone_name": "Asia/Kolkata",
        "registration_deadline": None,
        "capacity": None,
        "external_webinar_provider": "not_configured",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                request = route.request
                path = urlparse(request.url).path

                if path == "/api/auth/me":
                    _fulfill_json(
                        route,
                        {
                            "authenticated": True,
                            "user": {
                                "user_id": "webinar-browser-user",
                                "email": "webinar-publisher@example.test",
                                "is_admin": False,
                                "workspace_id": "webinar-browser-workspace",
                                "workspace_role": "owner",
                            },
                            "csrf_token": "webinar-browser-csrf-token",
                        },
                    )
                    return

                if path == "/api/workspaces":
                    _fulfill_json(
                        route,
                        {
                            "active_workspace_id": "webinar-browser-workspace",
                            "data": [
                                {
                                    "id": "webinar-browser-workspace",
                                    "name": "Webinar Browser Test Workspace",
                                    "role": "owner",
                                    "is_active": True,
                                    "lifecycle_state": "active",
                                }
                            ],
                        },
                    )
                    return

                if path == "/api/status":
                    _fulfill_json(
                        route,
                        {
                            "app_name": "OmniAffiliateOS",
                            "environment": "test",
                            "execution_mode": "SEMI_AUTONOMOUS",
                            "knowledge_index_available": False,
                            "api_model_configured": False,
                            "email_delivery_configured": False,
                            "video_rendering_available": False,
                            "publishing_dry_run": True,
                            "ad_automation_execute": False,
                            "clicks": 0,
                            "conversion_events": 0,
                            "commission_recorded": 0,
                        },
                    )
                    return

                if path == "/api/resource-budget":
                    _fulfill_json(
                        route,
                        {
                            "daily_budget_usd": 10,
                            "daily_estimated_used_usd": 0,
                            "daily_estimated_remaining_usd": 10,
                            "niche_budget_usd": 10,
                            "note": "Browser-test budget fixture",
                        },
                    )
                    return

                if path == "/api/integrations":
                    _fulfill_json(
                        route,
                        {
                            "total": 0,
                            "counts": {"enabled": 0, "configured": 0},
                            "items": [],
                            "verification_policy": "Browser-test fixture only",
                        },
                    )
                    return

                if path == "/api/capabilities":
                    _fulfill_json(
                        route,
                        {
                            "statuses": [],
                            "counts": {},
                            "items": [],
                            "provider_items": [],
                            "global_policy": "Browser-test fixture only",
                        },
                    )
                    return

                if path == "/api/webinars" and request.method == "POST":
                    submitted_events.append(json.loads(request.post_data or "{}"))
                    _fulfill_json(route, event_result, status=201)
                    return

                if path.startswith("/api/"):
                    _fulfill_json(route, {"detail": "Unexpected API request"}, status=404)
                    return

                route.continue_()

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Growth command center.").wait_for(state="visible")

            page.locator("#webinars").scroll_into_view_if_needed()
            page.locator("#webinar-title").fill("Browser regression webinar")
            page.locator("#webinar-host").fill("Example Presenter")
            page.locator("#webinar-summary").fill(
                "A practical product education session for publishers."
            )
            page.locator("#webinar-description").fill(
                "This session demonstrates a responsible content workflow, evidence checks, "
                "affiliate disclosure practice, and a guided product demonstration."
            )
            page.locator("#webinar-start").fill("2099-01-01T10:00")
            page.locator("#webinar-end").fill("2099-01-01T11:00")
            page.locator("#webinar-zone").fill("Asia/Kolkata")
            page.locator("#webinar-agenda").fill("\n".join(expected_agenda))
            page.locator("#webinar-privacy").fill(
                "https://publisher.example.test/privacy"
            )
            page.locator("#webinar-consent").fill(
                "I agree to use my details for webinar registration and administration."
            )

            with page.expect_response(
                lambda response: (
                    urlparse(response.url).path == "/api/webinars"
                    and response.request.method == "POST"
                )
            ) as response_info:
                page.locator("#webinars button[type='submit']").click()

            response = response_info.value
            assert response.status == 201, response.text()
            assert len(submitted_events) == 1
            assert submitted_events[0]["agenda_items"] == [
                {"title": expected_agenda[0], "description": ""},
                {"title": expected_agenda[1], "description": ""},
            ]
            assert submitted_events[0]["timezone_name"] == "Asia/Kolkata"
            assert event_result["external_webinar_provider"] == "not_configured"
        finally:
            browser.close()
