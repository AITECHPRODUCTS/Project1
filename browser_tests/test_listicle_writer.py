from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("BROWSER_BASE_URL", "http://127.0.0.1:3100")
PRODUCTS = [
    {
        "name": f"Tool {i}",
        "facts": {"Price": "Not supplied — verify", "Best for": f"Audience {i}"},
        "source_urls": [],
        "affiliate_relationship": "editorial",
    }
    for i in range(1, 6)
]


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


def test_listicle_writer_persists_and_opens_review_required_draft():
    posted = []
    result = {
        "asset_id": "listicle-asset-1",
        "asset_status": "draft",
        "revision_number": 1,
        "revision_of_asset_id": None,
        "revision_root_asset_id": "listicle-asset-1",
        "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
        "tone": "professional",
        "title": "5 Best Email Marketing Tools in 2026 (Evidence-Aware Roundup)",
        "slug": "best-email-marketing-tools-2026",
        "meta_description": "Evidence-aware roundup draft",
        "topic": "Email marketing tools",
        "audience": "Small publishers",
        "target_keyword": "best email marketing tools",
        "format": "listicle",
        "html": "<!doctype html><html><body><article><h1>Sandboxed preview</h1><p>Review the details.</p></article></body></html>",
        "word_count": 1300,
        "minimum_word_target": 1500,
        "minimum_word_target_met": False,
        "word_count_warning": "Draft below requested word target.",
        "product_count": 5,
        "products": PRODUCTS,
        "products_featured": [
            {"rank": i, "name": product["name"], "affiliate_relationship": "editorial", "affiliate_url": None}
            for i, product in enumerate(PRODUCTS, start=1)
        ],
        "evaluation_criteria": ["Audience fit", "Pricing", "Features"],
        "source_urls": [],
        "source_snapshots": [],
        "fact_evidence": [
            {"product": product["name"], "fact_name": "Price", "supplied_value": "Not supplied — verify",
             "source_id": None, "source_url": None, "excerpt_sha256": None, "exact_text_match": False,
             "evidence_status": "not_supplied", "editorial_review_required": True}
            for product in PRODUCTS
        ],
        "evidence_summary": {
            "source_count": 0, "source_snapshots_fetched": 0, "source_snapshots_failed": 0,
            "fact_count": 5, "exact_text_match_count": 0, "exact_text_not_found_count": 0,
            "facts_not_compared": 5, "interpretation": "Text presence is not fact verification.",
        },
        "evidence_status": "operator_supplied_unverified",
        "source_freshness": {"policy_version": 1, "checked_at": "2026-10-29T00:00:00+00:00", "max_age_hours": 24, "future_tolerance_seconds": 300, "status": "no_sources_supplied", "source_count": 0, "fresh_count": 0, "blocked_count": 0, "approval_allowed": True, "capture_window_satisfied": False, "message": "No sources were supplied. Editorial review may proceed, but product facts and currentness remain unverified.", "items": []},
        "product_facts_independently_verified": False,
        "external_product_sources_fetched": False,
        "requires_review": True,
        "publishing_started": False,
        "provider_write_access_verified": False,
        "provider": "test-model",
        "execution_boundary": "Workspace draft only. No publication.",
        "content_sha256": "a" * 64,
        "source_snapshot_manifest_sha256": "b" * 64,
        "evidence_payload_sha256": "c" * 64,
        "content_integrity_status": "verified",
        "review_status": "pending_review",
        "review_history": [],
        "reviewed_by": None,
        "reviewed_at": None,
        "reviewer_role": None,
        "reviewer_notes": None,
        "can_review": True,
    }
    saved = []
    results_by_id = {"listicle-asset-1": result}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def auth(route):
                _fulfill_json(route, {"csrf_token": "browser-test-csrf"})

            def list_drafts(route):
                _fulfill_json(route, {"items": saved, "total": len(saved), "limit": 20, "offset": 0})

            def create_draft(route):
                payload = json.loads(route.request.post_data or "{}")
                posted.append(payload)
                parent_id = payload.get("revision_of_asset_id")
                asset_id = "listicle-asset-2" if parent_id else "listicle-asset-1"
                number = 2 if parent_id else 1
                saved_result = {
                    **result,
                    "asset_id": asset_id,
                    "title": payload.get("topic", result["topic"]) + " (Evidence-Aware Roundup)",
                    "topic": payload.get("topic", result["topic"]),
                    "revision_number": number,
                    "revision_of_asset_id": parent_id,
                    "revision_root_asset_id": parent_id or asset_id,
                    "content_sha256": ("d" if parent_id else "a") * 64,
                }
                results_by_id[asset_id] = saved_result
                saved.insert(0, {
                    "asset_id": asset_id, "title": saved_result["title"], "asset_status": "draft",
                    "created_at": "2026-10-29T00:00:00+00:00", "product_count": 5, "word_count": 1300,
                    "evidence_status": "operator_supplied_unverified", "review_status": "pending_review",
                    "content_integrity_status": "verified", "publishing_started": False,
                    "revision_number": number, "revision_of_asset_id": parent_id,
                    "revision_root_asset_id": parent_id or asset_id,
                })
                _fulfill_json(route, saved_result, 201)

            def detail(route):
                asset_id = route.request.url.rstrip("/").split("/")[-1]
                _fulfill_json(route, results_by_id.get(asset_id, result))

            page.route("**/api/auth/me", auth)
            page.route("**/api/content/listicle", create_draft)
            page.route("**/api/content/listicles?*", list_drafts)
            page.route("**/api/content/listicles/**", detail)
            page.goto(f"{BASE_URL}/listicle-writer", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Evidence-aware listicle writer").wait_for(state="visible")
            page.locator("#listicle-products").fill(json.dumps(PRODUCTS))
            page.get_by_role("button", name="Generate listicle draft").click()
            page.get_by_text("Source snapshots", exact=True).wait_for(state="visible")
            page.get_by_text("operator supplied unverified", exact=False).first.wait_for(state="visible")
            page.get_by_text("Source freshness: no sources supplied", exact=False).first.wait_for(state="visible")
            page.get_by_text("Not supplied — verify", exact=False).first.wait_for(state="visible")
            page.get_by_title("Listicle article preview").wait_for(state="visible")
            assert len(posted) == 1
            assert posted[0]["topic"] == "Email marketing tools for small publishers"
            assert len(posted[0]["products"]) == 5
            assert posted[0]["products"][0]["name"] == "Tool 1"
            assert "Published: No" in page.locator("main").inner_text()
            page.get_by_role("button", name="Open draft").wait_for(state="visible")
            page.get_by_role("button", name="Open draft").click()
            page.get_by_role("button", name="Revise saved draft").wait_for(state="visible")
            page.get_by_role("button", name="Revise saved draft").click()
            page.get_by_role("textbox", name="Topic or category").fill("Email marketing tools — revision")
            page.get_by_role("button", name="Generate listicle revision").click()
            page.get_by_text("Revision #2", exact=False).first.wait_for(state="visible")
            assert len(posted) == 2
            assert posted[1]["revision_of_asset_id"] == "listicle-asset-1"
            assert posted[1]["topic"] == "Email marketing tools — revision"
            assert posted[1]["products"][0]["name"] == "Tool 1"
            assert "Original draft remains unchanged" in page.locator("main").inner_text()
        finally:
            browser.close()


def test_listicle_writer_rejects_four_products_without_api_write():
    posted = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def auth(route):
                _fulfill_json(route, {"csrf_token": "browser-test-csrf"})

            def no_drafts(route):
                _fulfill_json(route, {"items": [], "total": 0, "limit": 20, "offset": 0})

            def create_draft(route):
                posted.append(route.request.url)
                _fulfill_json(route, {}, status=201)

            page.route("**/api/auth/me", auth)
            page.route("**/api/content/listicle", create_draft)
            page.route("**/api/content/listicles?*", no_drafts)
            page.goto(f"{BASE_URL}/listicle-writer", wait_until="domcontentloaded")
            page.locator("#listicle-products").fill(json.dumps(PRODUCTS[:4]))
            page.get_by_role("button", name="Generate listicle draft").click()
            page.get_by_role("alert").get_by_text("Supply between five and twelve product objects.").wait_for(state="visible")
            assert posted == []
        finally:
            browser.close()
