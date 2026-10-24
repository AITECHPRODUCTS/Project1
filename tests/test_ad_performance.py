from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend.main import app
from backend.schemas import AdPerformanceObservationRequest


def test_observation_request_rejects_negative_money_and_unsafe_source_urls():
    with pytest.raises(ValidationError):
        AdPerformanceObservationRequest(
            platform="meta",
            creative_id="meta-01",
            spend_usd="-0.01",
            commission_usd="0.00",
        )
    with pytest.raises(ValidationError):
        AdPerformanceObservationRequest(
            platform="meta",
            creative_id="meta-01",
            source_reference_url="javascript:alert(1)",
        )


def test_reported_ad_metrics_are_persisted_but_not_treated_as_verified():
    payload = {
        "platform": "meta",
        "creative_id": "test-creative-reported-metrics",
        "source_type": "provider_export",
        "source_reference_url": "https://reports.example/campaigns/123",
        "impressions": 1000,
        "clicks": 42,
        "conversions": 3,
        "spend_usd": "10.00",
        "commission_usd": "25.00",
        "currency": "usd",
        "note": "Imported report for QA",
    }

    with TestClient(app) as client:
        created = client.post("/api/ads/observations", json=payload)
        assert created.status_code == 201, created.text
        row = created.json()
        assert row["evidence_status"] == "operator_supplied_unverified"
        assert row["currency"] == "USD"
        assert row["spend_usd"] == "10.00"
        assert row["external_actions_executed"] is False
        assert row["optimization_eligible"] is False

        listing = client.get("/api/ads/observations?limit=50")
        assert listing.status_code == 200, listing.text
        assert any(item["id"] == row["id"] for item in listing.json()["data"])

        performance = client.get("/api/ads/performance?limit=50")
        assert performance.status_code == 200, performance.text
        summary = next(
            item for item in performance.json()["items"]
            if item["creative_id"] == "test-creative-reported-metrics"
        )
        assert summary["reported_metrics_unverified"]["impressions"] == 1000
        assert summary["reported_metrics_unverified"]["clicks"] == 42
        assert summary["reported_metrics_unverified"]["spend_usd"] == "10.00"
        assert summary["reported_metrics_unverified"]["commission_to_spend_ratio"] == 2.5
        assert summary["verified_metrics"] is None
        assert summary["optimization"]["eligible"] is False
        assert summary["optimization"]["automatic_action_executed"] is False


def test_ad_observation_links_must_reference_a_plan_in_the_active_workspace():
    payload = {
        "campaign_plan_id": "missing-plan",
        "platform": "meta",
        "creative_id": "meta-01",
        "spend_usd": "0.00",
        "commission_usd": "0.00",
    }
    with TestClient(app) as client:
        response = client.post("/api/ads/observations", json=payload)
        assert response.status_code == 404
