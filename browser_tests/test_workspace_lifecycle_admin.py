from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")
ADMIN_WORKSPACE = "10000000-0000-4000-8000-000000000001"
TARGET_WORKSPACE = "10000000-0000-4000-8000-000000000002"


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


def test_platform_admin_tenant_lifecycle_suspends_and_reinstates_with_reason():
    tenants = [
        {
            "id": ADMIN_WORKSPACE, "name": "Platform operations", "slug": "platform-operations",
            "owner_user_id": "admin-user", "active_memberships": 1, "created_at": None,
            "lifecycle_state": "active", "suspended_at": None, "suspended_by": None, "suspension_reason": None,
        },
        {
            "id": TARGET_WORKSPACE, "name": "Demo affiliate tenant", "slug": "demo-affiliate-tenant",
            "owner_user_id": "tenant-owner", "active_memberships": 2, "created_at": None,
            "lifecycle_state": "active", "suspended_at": None, "suspended_by": None, "suspension_reason": None,
        },
    ]
    posts = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_api(route):
                request = route.request
                url = request.url
                if url.endswith("/api/auth/me"):
                    _fulfill_json(route, {"authenticated": True, "csrf_token": "tenant-admin-csrf"})
                    return
                if "/api/admin/tenants/" in url and request.method == "POST":
                    body = json.loads(request.post_data or "{}")
                    posts.append({"url": url, "body": body})
                    row = next(item for item in tenants if item["id"] == TARGET_WORKSPACE)
                    action = "suspend" if url.endswith("/suspend") else "reinstate"
                    if action == "suspend":
                        row.update({
                            "lifecycle_state": "suspended",
                            "suspended_at": "2026-10-29T12:00:00+00:00",
                            "suspended_by": "platform.operator@example.invalid",
                            "suspension_reason": body["reason"],
                        })
                    else:
                        row.update({
                            "lifecycle_state": "active",
                            "suspended_at": None,
                            "suspended_by": None,
                            "suspension_reason": None,
                        })
                    _fulfill_json(route, row)
                    return
                if url.endswith("/api/admin/tenants?limit=100"):
                    _fulfill_json(route, {
                        "count": len(tenants), "limit": 100, "read_only": True,
                        "lifecycle_mutations_available": True, "active_workspace_id": ADMIN_WORKSPACE,
                        "data": tenants,
                    })
                    return
                _fulfill_json(route, {"detail": "Unexpected request"}, status=404)

            page.route("**/api/**", handle_api)
            page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Tenant lifecycle console").wait_for(state="visible")
            page.get_by_text("Current administrative workspace is protected from self-suspension.").wait_for(state="visible")

            page.get_by_label("Audit reason for Demo affiliate tenant").fill("Confirmed abuse after support investigation")
            page.get_by_role("button", name="Suspend Demo affiliate tenant").click()
            page.get_by_text("Demo affiliate tenant workspace suspended. The transition and reason were added to the audit trail.").wait_for(state="visible")
            assert len(posts) == 1
            assert posts[0]["body"]["reason"] == "Confirmed abuse after support investigation"
            page.get_by_text("suspended", exact=True).wait_for(state="visible")

            page.get_by_label("Audit reason for Demo affiliate tenant").fill("Appeal reviewed and access restored")
            page.get_by_role("button", name="Reinstate Demo affiliate tenant").click()
            page.get_by_text("Demo affiliate tenant workspace active. The transition and reason were added to the audit trail.").wait_for(state="visible")
            assert len(posts) == 2
            assert posts[1]["body"]["reason"] == "Appeal reviewed and access restored"
        finally:
            browser.close()
