from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:3100"


def _json(route, payload: dict) -> None:
    route.fulfill(
        status=200,
        content_type="application/json",
        headers={
            "access-control-allow-origin": "http://127.0.0.1:3100",
            "access-control-allow-credentials": "true",
        },
        body=json.dumps(payload),
    )


def test_content_decay_review_ui_posts_supplied_evidence_and_renders_review_only_report():
    posted: list[dict] = []
    report = {
        "asset_id": "content-decay-asset-123",
        "site": "https://example.com",
        "timeframe": "90d",
        "timeframe_label": "90 days",
        "pages_analyzed": 1,
        "pages_decaying": 1,
        "total_refresh_effort_hours": 2.5,
        "decaying_pages": [{
            "url": "https://example.com/best-tools",
            "title": "Best tools",
            "target_keyword": "best tools",
            "priority": "P1-high",
            "priority_score": 44.0,
            "decay_signals": ["clicks_declined_20_percent_or_more"],
            "preliminary_signals": [],
            "refresh_actions": ["Compare affected query and device segments."],
            "estimated_effort_hours": 2.5,
            "effort_source": "heuristic_estimate",
            "revenue_impact": "medium",
            "metrics": {
                "clicks_decline_pct": 35.0,
                "impressions_decline_pct": 25.0,
                "position_worsening": 9.0,
            },
            "evidence_confidence": "medium",
            "data_provenance": "operator_supplied_unverified",
            "requires_review": True,
        }],
        "healthy_pages": [],
        "pages_needing_more_data": [{
            "url": "https://example.com/new-guide",
            "title": "New guide",
            "missing_data": ["matched previous/current click totals"],
            "preliminary_signals": [],
            "data_provenance": "operator_supplied_unverified",
        }],
        "priority_queues": {
            "P0-critical": [],
            "P1-high": ["https://example.com/best-tools"],
            "P2-medium": [],
            "P3-low": [],
        },
        "search_console_connected": False,
        "competitor_data_checked": False,
        "external_search_performed": False,
        "metrics_source": "operator_supplied_unverified",
        "traffic_recovery_estimate_supported": False,
        "requires_review": True,
        "publishing_started": False,
        "note": "Supplied metrics only. No crawl or traffic-recovery prediction.",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def auth_me(route):
                _json(route, {
                    "authenticated": True,
                    "user": {
                        "email": "content-editor@example.invalid",
                        "is_admin": False,
                        "workspace_id": "browser-workspace",
                        "workspace_role": "owner",
                    },
                    "csrf_token": "browser-csrf-token",
                })

            def content_decay(route):
                assert route.request.method == "POST"
                posted.append(json.loads(route.request.post_data or "{}"))
                _json(route, report)

            page.route("**/api/auth/me", auth_me)
            page.route("**/api/research/content-decay", content_decay)
            page.goto(f"{BASE_URL}/content-decay", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Content decay review queue").wait_for(state="visible")
            assert page.get_by_label("Public site URL").input_value() == "https://example.com"
            assert "does not connect to Search Console" in page.locator("main").inner_text()

            page.get_by_role("button", name="Build and save review queue").click()
            page.get_by_text("Review draft saved.", exact=False).wait_for(state="visible")
            page.get_by_role("heading", name="Priority review queue").wait_for(state="visible")
            page.get_by_text("P1-high · 44", exact=False).wait_for(state="visible")
            page.get_by_text("35% decline", exact=False).wait_for(state="visible")
            page.get_by_role("heading", name="Pages needing more data").wait_for(state="visible")
            assert page.get_by_text("Publishing was not started.", exact=False).is_visible()
            assert len(posted) == 1
            assert posted[0]["site_url"] == "https://example.com"
            assert posted[0]["timeframe"] == "90d"
            assert len(posted[0]["pages"]) == 1
            assert posted[0]["pages"][0]["url"] == "https://example.com/best-tools"
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()
