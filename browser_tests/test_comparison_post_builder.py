from __future__ import annotations

import json
import os
from urllib.parse import urlsplit

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


def test_comparison_writer_saves_review_draft_and_displays_unknown_facts():
    posted = []
    saved_items = []
    result = {
        "asset_id": "comparison-asset-1",
        "asset_status": "draft",
        "title": "Analytics comparison — Product Comparison",
        "html": "<!doctype html><html><body><article><h1>Isolated article</h1><p>Preview text</p></article></body></html>",
        "word_count": 604,
        "minimum_word_target": 500,
        "minimum_word_target_met": True,
        "word_count_warning": None,
        "product_count": 2,
        "products": [
            {"name": "Product Alpha", "facts": {"Price": "Not supplied"}, "source_urls": []},
            {"name": "Product Beta", "facts": {"Price": "$49/month"}, "source_urls": []},
        ],
        "decision_criteria": ["Price"],
        "comparison_table": [{
            "criterion": "Price",
            "values": [
                {"product": "Product Alpha", "value": "Not supplied — verify"},
                {"product": "Product Beta", "value": "$49/month"},
            ],
        }],
        "unknown_fact_count": 1,
        "source_urls": ["https://vendor.example/alpha"],
        "source_snapshots": [{"source_id": "S01", "url": "https://vendor.example/alpha", "product_names": ["Product Alpha"], "title": "Alpha evidence", "status": "fetched", "http_status": 200, "content_type": "text/html", "fetched_at": "2026-10-29T00:00:00+00:00", "excerpt": "Price $20 appears in the captured page.", "excerpt_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "error_type": None, "detail": None}],
        "fact_evidence": [{"product": "Product Alpha", "fact_name": "Price", "supplied_value": "Not supplied — verify", "source_id": None, "source_url": None, "excerpt_sha256": None, "exact_text_match": False, "evidence_status": "not_supplied", "editorial_review_required": True}],
        "evidence_summary": {"source_count": 1, "source_snapshots_fetched": 1, "source_snapshots_failed": 0, "fact_count": 1, "exact_text_match_count": 0, "exact_text_not_found_count": 0, "facts_not_compared": 1, "interpretation": "A text match is not fact verification."},
        "evidence_status": "public_snapshot_captured_not_fact_verified",
        "product_facts_independently_verified": False,
        "external_product_sources_fetched": False,
        "requires_review": True,
        "publishing_started": False,
        "provider_write_access_verified": False,
        "provider": "test-model",
        "execution_boundary": "Draft only; product evidence not verified.",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_auth(route):
                _fulfill_json(route, {"csrf_token": "browser-test-csrf"})

            def handle_comparison(route):
                posted.append(json.loads(route.request.post_data or "{}"))
                saved_items.insert(0, {
                    "asset_id": result["asset_id"], "title": result["title"], "asset_status": "draft",
                    "created_at": "2026-10-29T00:00:00+00:00", "word_count": result["word_count"],
                    "product_count": result["product_count"], "unknown_fact_count": result["unknown_fact_count"],
                    "evidence_status": result["evidence_status"], "source_snapshots_fetched": 1,
                    "requires_review": True, "publishing_started": False,
                })
                _fulfill_json(route, result, status=201)

            def handle_saved(route):
                path = urlsplit(route.request.url).path.rstrip("/")
                if path.endswith("/api/content/comparison-posts"):
                    _fulfill_json(route, {"items": list(saved_items), "total": len(saved_items), "limit": 20, "offset": 0})
                else:
                    _fulfill_json(route, result)

            page.route("**/api/auth/me", handle_auth)
            page.route("**/api/content/comparison-post", handle_comparison)
            page.route("**/api/content/comparison-posts**", handle_saved)
            page.goto(f"{BASE_URL}/comparison-post", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Product comparison writer").wait_for(state="visible")
            page.locator("#comparison-products").fill(json.dumps([
                {"name": "Product Alpha", "facts": {"Price": "Not supplied — verify"}, "source_urls": []},
                {"name": "Product Beta", "facts": {"Price": "$49/month"}, "source_urls": []},
            ]))
            page.get_by_role("button", name="Generate comparison draft").click()
            page.get_by_text("Unknown table cells", exact=True).wait_for(state="visible")
            page.get_by_text("Fetched snapshots", exact=True).wait_for(state="visible")
            page.get_by_text("S01 · Alpha evidence · fetched", exact=True).wait_for(state="visible")
            page.get_by_text("Not supplied — verify", exact=True).first.wait_for(state="visible")
            page.get_by_text("public snapshot captured not fact verified", exact=False).first.wait_for(state="visible")
            page.get_by_title("Comparison article preview").wait_for(state="visible")
            assert len(posted) == 1
            assert posted[0]["topic"] == "Affiliate analytics tools compared"
            assert posted[0]["products"][0]["name"] == "Product Alpha"
            assert page.locator("main [role='alert']").count() == 0
            assert "Published: No" in page.locator("main").inner_text()
            page.get_by_role("button", name="Open draft").wait_for(state="visible")
            page.get_by_role("button", name="Open draft").click()
            page.get_by_text("Opened saved comparison draft.", exact=False).wait_for(state="visible")
        finally:
            browser.close()


def test_comparison_writer_rejects_invalid_json_without_api_write():
    posted = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_auth(route):
                _fulfill_json(route, {"csrf_token": "browser-test-csrf"})

            def handle_comparison(route):
                posted.append(route.request.url)
                _fulfill_json(route, {}, status=201)

            page.route("**/api/auth/me", handle_auth)
            page.route("**/api/content/comparison-post", handle_comparison)
            page.route("**/api/content/comparison-posts**", lambda route: _fulfill_json(route, {"items": [], "total": 0, "limit": 20, "offset": 0}))
            page.goto(f"{BASE_URL}/comparison-post", wait_until="domcontentloaded")
            page.locator("#comparison-products").fill("[")
            page.get_by_role("button", name="Generate comparison draft").click()
            page.get_by_role("alert").get_by_text("Products must be valid JSON.").wait_for(state="visible")
            assert posted == []
        finally:
            browser.close()


def test_saved_comparison_draft_can_be_reopened_after_page_reload():
    stored = {
        "asset_id": "saved-comparison-77",
        "asset_status": "draft",
        "title": "Saved analytics products — Product Comparison",
        "html": "<!doctype html><html><body><article><h1>Saved draft preview</h1></article></body></html>",
        "word_count": 450,
        "minimum_word_target": 500,
        "minimum_word_target_met": False,
        "word_count_warning": "Saved draft is below target.",
        "product_count": 2,
        "products": [
            {"name": "Product Alpha", "facts": {"Price": "$20"}, "source_urls": []},
            {"name": "Product Beta", "facts": {"Price": "$35"}, "source_urls": []},
        ],
        "decision_criteria": ["Price"],
        "comparison_table": [{"criterion": "Price", "values": [
            {"product": "Product Alpha", "value": "$20"},
            {"product": "Product Beta", "value": "$35"},
        ]}],
        "unknown_fact_count": 0,
        "source_urls": [],
        "source_snapshots": [],
        "fact_evidence": [],
        "evidence_summary": {"source_snapshots_fetched": 0, "exact_text_match_count": 0, "exact_text_not_found_count": 0},
        "evidence_status": "source_fetch_failed_unverified",
        "product_facts_independently_verified": False,
        "external_product_sources_fetched": False,
        "requires_review": True,
        "publishing_started": False,
        "provider_write_access_verified": False,
        "provider": "test-model",
        "execution_boundary": "Saved workspace review draft; not published.",
    }
    detail_calls = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def handle_auth(route):
                _fulfill_json(route, {"csrf_token": "browser-test-csrf"})

            def handle_saved(route):
                path = route.request.url.split("?", 1)[0].rstrip("/")
                if path.endswith("/api/content/comparison-posts"):
                    _fulfill_json(route, {
                        "items": [{
                            "asset_id": stored["asset_id"], "title": stored["title"], "asset_status": "draft",
                            "created_at": "2026-10-29T00:00:00+00:00", "word_count": stored["word_count"],
                            "product_count": stored["product_count"], "unknown_fact_count": stored["unknown_fact_count"],
                            "evidence_status": stored["evidence_status"], "source_snapshots_fetched": 0,
                            "requires_review": True, "publishing_started": False,
                        }], "total": 1, "limit": 20, "offset": 0,
                    })
                else:
                    detail_calls.append(path)
                    _fulfill_json(route, stored)

            page.route("**/api/auth/me", handle_auth)
            page.route("**/api/content/comparison-posts**", handle_saved)
            page.goto(f"{BASE_URL}/comparison-post", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Product comparison writer").wait_for(state="visible")
            page.get_by_role("button", name="Open draft").click()
            page.get_by_role("heading", name="Saved analytics products — Product Comparison").wait_for(state="visible")
            page.get_by_title("Comparison article preview").wait_for(state="visible")
            assert detail_calls == ["/api/content/comparison-posts/saved-comparison-77"]
            assert page.get_by_text("Published: No", exact=False).count() == 1
            assert page.locator("main [role='alert']").count() == 0
        finally:
            browser.close()

