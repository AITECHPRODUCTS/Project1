from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")


def _fulfill_json(route, payload: dict, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        headers={"access-control-allow-origin": "http://127.0.0.1:3100", "access-control-allow-credentials": "true"},
        body=json.dumps(payload),
    )


def test_platform_admin_operations_console_renders_read_only_evidence():
    overview = {
        "counts": {"users": 18, "workspaces": 7, "active_workspace_memberships": 21, "workflow_runs_persisted": 42, "audit_events_persisted": 109},
        "runtime": {"environment": "staging", "scheduler_running": True, "publishing_dry_run": True, "ad_automation_execute": False, "durable_queue_status": "not_verified_by_this_endpoint"},
        "release": {"deployment_verification": "not_asserted", "note": "Runtime observations do not certify a production release."},
    }
    workflows = {"data": [{
        "id": "workflow-run-42", "workspace_id": "workspace-7", "workflow_name": "full_flywheel",
        "status": "paused_for_approval", "current_step": "S5", "execution_mode": "SEMI_AUTONOMOUS",
        "has_error": False, "created_at": "2026-10-30T08:00:00+00:00",
    }]}
    integrations = {"items": [{
        "provider_id": "openaffiliate", "display_name": "OpenAffiliate", "status": "not_configured",
        "write_access_verified": False, "reason": "Account authorization and live contract are not verified.",
    }]}
    audits = {"data": [{
        "id": 109, "workspace_id": "workspace-7", "actor": "operator@example.invalid",
        "action": "platform.outbound_actions.paused", "resource_type": "platform_execution_control",
        "resource_id": "1", "outcome": "paused",
    }]}
    capabilities = {
        "statuses": ["automatic", "automatic_after_one_time_authorization", "approval_required", "partially_available", "manual_provider_flow", "not_supported", "not_configured"],
        "counts": {"automatic": 2, "approval_required": 3, "partially_available": 2, "not_configured": 5},
        "items": [
            {
                "id": "super_admin_operations",
                "title": "Platform-wide Super Admin and tenant operations",
                "status": "partially_available",
                "reason": "Implemented foundations include audited tenant suspend/reinstate and read-only operational views; dead-letter recovery remains incomplete.",
                "prerequisites": ["Separate platform-admin identity", "Worker/queue and dead-letter operations"],
                "external_side_effect": False,
            },
            {
                "id": "offer_discovery",
                "title": "Affiliate offer discovery",
                "status": "partially_available",
                "reason": "A directory adapter is configured but live health and contract verification have not passed.",
                "prerequisites": ["Provider terms review", "Live read-only contract test"],
                "external_side_effect": False,
            },
        ],
        "provider_items": [{
            "provider_id": "openaffiliate",
            "display_name": "OpenAffiliate",
            "status": "partially_available",
            "registry_status": "configured_not_health_checked",
            "adapter": "openaffiliate",
            "reason": "Configured, not health checked",
            "external_side_effect": False,
        }],
        "global_policy": "No integration is considered connected from configuration alone.",
    }
    tenants = {"count": 0, "limit": 100, "read_only": True, "lifecycle_mutations_available": True, "active_workspace_id": "workspace-admin", "data": []}
    control = {
        "id": 1, "outbound_actions_paused": True, "reason": "Security incident investigation",
        "changed_by": "operator@example.invalid", "changed_at": "2026-10-30T08:05:00+00:00",
        "enforcement_scope": "registry-gated writes", "completed_idempotency_replays_allowed": True,
        "in_flight_actions_cancelled": False, "note": "Only new registry-gated writes are paused.",
    }
    seen: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                url = route.request.url
                seen.append(url)
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "operator@example.invalid",
                            "account_type": "platform_admin",
                            "is_admin": True,
                        },
                    })
                elif "/api/admin/overview" in url:
                    _fulfill_json(route, overview)
                elif "/api/admin/workflows?" in url:
                    _fulfill_json(route, workflows)
                elif "/api/integrations" in url:
                    _fulfill_json(route, integrations)
                elif "/api/admin/audit?" in url:
                    _fulfill_json(route, audits)
                elif url.endswith("/api/capabilities"):
                    _fulfill_json(route, capabilities)
                elif url.endswith("/api/admin/execution-control"):
                    _fulfill_json(route, control)
                elif "/api/admin/tenants?" in url:
                    _fulfill_json(route, tenants)
                else:
                    _fulfill_json(route, {"detail": "Unexpected request"}, status=404)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/admin", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Platform operations overview").wait_for(state="visible")
            admin_nav = page.get_by_role("navigation", name="Platform administrator navigation")
            assert admin_nav.get_by_role("link", name="Growth command").get_attribute("href") == "/"
            assert admin_nav.get_by_role("link", name="Operations overview").get_attribute("href") == "#platform-operations-title"
            assert admin_nav.get_by_role("link", name="Tenant lifecycle").get_attribute("href") == "#tenant-lifecycle"
            audit_export = page.get_by_test_id("platform-audit-export")
            assert audit_export.get_attribute("href").endswith("/api/admin/audit/export.csv?limit=500")
            assert "Export latest 500 audit rows" in audit_export.inner_text()
            assert page.get_by_test_id("platform-metric-users").inner_text() == "18"
            assert page.get_by_test_id("platform-metric-workspaces").inner_text() == "7"
            assert page.get_by_test_id("platform-metric-workflows").inner_text() == "42"
            assert page.get_by_test_id("platform-queue-state").inner_text() == "not verified by this endpoint"
            assert page.get_by_test_id("platform-workflow-workflow-run-42").is_visible()
            assert page.get_by_test_id("provider-readiness-openaffiliate").get_by_text("not configured").is_visible()
            assert page.get_by_test_id("provider-readiness-openaffiliate").get_by_text("Write access: not verified").is_visible()
            assert page.get_by_test_id("platform-audit-109").is_visible()
            admin_capability = page.get_by_test_id("platform-capability-super_admin_operations")
            assert admin_capability.is_visible()
            assert admin_capability.get_by_text("partially available").is_visible()
            assert admin_capability.get_by_text("dead-letter recovery remains incomplete").is_visible()
            offer_capability = page.get_by_test_id("platform-capability-offer_discovery")
            assert offer_capability.get_by_text("partially available").is_visible()
            assert page.get_by_test_id("provider-capability-openaffiliate").get_by_text("partially available").is_visible()
            assert any("/api/capabilities" in url for url in seen)
            assert any("/api/admin/overview" in url for url in seen)
            assert any("/api/admin/workflows?limit=20" in url for url in seen)
            assert any("/api/integrations" in url for url in seen)
            assert any("/api/admin/audit?limit=20" in url for url in seen)
        finally:
            browser.close()

def test_business_persona_cannot_load_platform_admin_console_data():
    seen: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                url = route.request.url
                seen.append(url)
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "merchant@example.test",
                            "account_type": "merchant_product_owner",
                            "is_admin": False,
                        },
                    })
                else:
                    _fulfill_json(route, {"detail": "Forbidden"}, status=403)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/admin", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Platform administrator access required").wait_for()
            assert not any("/api/admin/" in url for url in seen)
            assert not any("/api/capabilities" in url for url in seen)
            assert not any("/api/integrations" in url for url in seen)
        finally:
            browser.close()



def test_admin_flag_without_platform_admin_persona_cannot_open_admin_console():
    seen: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                seen.append(route.request.url)
                if route.request.url.endswith("/api/auth/me"):
                    _fulfill_json(route, {
                        "authenticated": True,
                        "user": {
                            "email": "merchant@example.test",
                            "account_type": "merchant_product_owner",
                            "is_admin": True,
                        },
                    })
                else:
                    _fulfill_json(route, {"detail": "Forbidden"}, status=403)

            page.route("**/api/**", handle_api)
            page.goto(BASE_URL + "/admin", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Platform administrator access required").wait_for(state="visible")
            assert sum(url.endswith("/api/auth/me") for url in seen) == 1
            assert not any("/api/admin/" in url for url in seen)
            assert not any("/api/capabilities" in url for url in seen)
        finally:
            browser.close()
