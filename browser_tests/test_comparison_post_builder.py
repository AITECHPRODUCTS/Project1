from __future__ import annotations

import json
import os

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
        "source_urls": [],
        "evidence_status": "operator_supplied_unverified",
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
                _fulfill_json(route, result, status=201)

            page.route("**/api/auth/me", handle_auth)
            page.route("**/api/content/comparison-post", handle_comparison)
            page.goto(f"{BASE_URL}/comparison-post", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Product comparison writer").wait_for(state="visible")
            page.locator("#comparison-products").fill(json.dumps([
                {"name": "Product Alpha", "facts": {"Price": "Not supplied — verify"}, "source_urls": []},
                {"name": "Product Beta", "facts": {"Price": "$49/month"}, "source_urls": []},
            ]))
            page.get_by_role("button", name="Generate comparison draft").click()
            page.get_by_text("Unknown table cells", exact=True).wait_for(state="visible")
            page.get_by_text("Not supplied — verify", exact=True).wait_for(state="visible")
            page.get_by_text("operator supplied unverified", exact=False).wait_for(state="visible")
            page.get_by_title("Comparison article preview").wait_for(state="visible")
            assert len(posted) == 1
            assert posted[0]["topic"] == "Affiliate analytics tools compared"
            assert posted[0]["products"][0]["name"] == "Product Alpha"
            assert page.locator("main [role='alert']").count() == 0
            assert "Published: No" in page.locator("main").inner_text()
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
            page.goto(f"{BASE_URL}/comparison-post", wait_until="domcontentloaded")
            page.locator("#comparison-products").fill("[")
            page.get_by_role("button", name="Generate comparison draft").click()
            page.get_by_role("alert").get_by_text("Products must be valid JSON.").wait_for(state="visible")
            assert posted == []
        finally:
            browser.close()
