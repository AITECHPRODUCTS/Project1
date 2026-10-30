from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_ad_plan_creation_is_persisted_and_readable():
    payload = {
        "campaign_name": "Persistence acceptance plan",
        "niche": "creator productivity workflows",
        "audience": "independent creators",
        "region": "US",
        "objective": "leads",
        "platforms": ["meta", "google_search"],
        "variants_per_platform": 2,
        "daily_budget_usd": "12.34",
        "evidence_urls": ["https://example.com/official-features"],
        "landing_page_url": "https://example.com/guide",
        "affiliate_disclosure": "Disclosure: I may earn a commission from qualifying purchases.",
    }

    with TestClient(app) as client:
        response = client.post("/api/ads/plan", json=payload)
        assert response.status_code == 201, response.text
        generated = response.json()
        plan_id = generated["plan_id"]

        assert generated["external_actions_executed"] is False
        assert generated["publishing_authorized"] is False
        assert generated["spend_authorized"] is False

        listing = client.get("/api/ads/plans?limit=20")
        assert listing.status_code == 200, listing.text
        listing_data = listing.json()
        saved = next(row for row in listing_data["data"] if row["id"] == plan_id)
        assert saved["status"] == "draft"
        assert saved["daily_budget_usd"] == "12.34"
        assert saved["creative_count"] == 4

        detail = client.get(f"/api/ads/plans/{plan_id}")
        assert detail.status_code == 200, detail.text
        detail_data = detail.json()
        assert detail_data["id"] == plan_id
        assert detail_data["plan"]["plan_id"] == plan_id
        assert detail_data["publishing_authorized"] is False
        assert detail_data["spend_authorized"] is False


def test_ad_plan_read_returns_404_for_unknown_id():
    with TestClient(app) as client:
        response = client.get("/api/ads/plans/does-not-exist")
        assert response.status_code == 404
